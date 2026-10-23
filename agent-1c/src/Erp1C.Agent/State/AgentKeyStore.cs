using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using Erp1C.Core.Crypto;
using Erp1C.Core.Json;
using Erp1C.Core.Security;
using Erp1C.Core.Storage;

namespace Erp1C.Agent.State
{
    /// <summary>agent.key file shape (34 §5.1).</summary>
    public sealed class AgentKeyFile
    {
        public int V { get; set; } = 1;

        public string Alg { get; set; } = "Ed25519";

        public string Kid { get; set; } = string.Empty;

        public string X { get; set; } = string.Empty;

        public string Protected { get; set; } = string.Empty;

        public string CreatedAt { get; set; } = string.Empty;
    }

    /// <summary>The DPAPI could not open agent.key (→ ONEC_DPAPI_FAILED, 34 §5.6).</summary>
    public sealed class AgentKeyUnavailableException : Exception
    {
        public AgentKeyUnavailableException()
        {
        }

        public AgentKeyUnavailableException(string message)
            : base(message)
        {
        }

        public AgentKeyUnavailableException(string message, Exception inner)
            : base(message, inner)
        {
        }
    }

    /// <summary>
    /// The agent's Ed25519 identity (34 §5.1): seed protected with DPAPI CurrentUser, entropy
    /// <c>ErpOneCAgent/agent.key/v1|&lt;machine_hash&gt;</c>; the private key is in memory only while signing and is
    /// zeroed right after.
    /// </summary>
    public sealed class AgentKeyStore
    {
        private readonly string _path;
        private readonly ISecretProtector _protector;
        private readonly string _machineHash;

        public AgentKeyStore(string path, ISecretProtector protector, string machineHash)
        {
            _path = path;
            _protector = protector;
            _machineHash = machineHash;
        }

        private string Purpose => "ErpOneCAgent/agent.key/v1|" + _machineHash;

        public bool Exists => File.Exists(_path);

        /// <summary>Loads the public part (no DPAPI).</summary>
        public AgentKeyFile? Read()
        {
            if (!File.Exists(_path)) return null;
            try
            {
                return AgentJson.Deserialize<AgentKeyFile>(File.ReadAllText(_path));
            }
            catch (JsonException)
            {
                return null;
            }
        }

        /// <summary>Creates a key pair if none exists and returns the public part.</summary>
        public AgentKeyFile EnsureKey(DateTimeOffset now)
        {
            var existing = Read();
            if (existing != null) return existing;
            var (seed, x) = Ed25519.Generate();
            try
            {
                var file = new AgentKeyFile
                {
                    Kid = JwkThumbprint.Ed25519(x),
                    X = Base64Url.Encode(x),
                    Protected = Convert.ToBase64String(_protector.Protect(seed, Purpose)),
                    CreatedAt = now.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture),
                };
                AtomicFile.WriteAllText(_path, AgentJson.Serialize(file));
                return file;
            }
            finally
            {
                Array.Clear(seed, 0, seed.Length);
            }
        }

        /// <summary>Signs with the private key; the seed is cleared right after use.</summary>
        public byte[] Sign(byte[] message)
        {
            var file = Read() ?? throw new AgentKeyUnavailableException("agent.key missing");
            byte[] seed;
            try
            {
                seed = _protector.Unprotect(Convert.FromBase64String(file.Protected), Purpose);
            }
            catch (Exception e) when (e is CryptographicException || e is FormatException)
            {
                throw new AgentKeyUnavailableException("agent.key cannot be opened (DPAPI)", e);
            }

            try
            {
                return Ed25519.Sign(seed, message);
            }
            finally
            {
                Array.Clear(seed, 0, seed.Length);
            }
        }

        public void Delete()
        {
            if (File.Exists(_path)) File.Delete(_path);
        }
    }
}
