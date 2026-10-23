using System;
using Org.BouncyCastle.Crypto.Generators;
using Org.BouncyCastle.Crypto.Parameters;
using Org.BouncyCastle.Crypto.Signers;
using Org.BouncyCastle.Security;

namespace Erp1C.Core.Crypto
{
    /// <summary>Ed25519 (RFC 8032) through BouncyCastle — pure managed, AnyCPU (34 §2.3).</summary>
    public static class Ed25519
    {
        public const int KeySize = 32;
        public const int SignatureSize = 64;

        /// <summary>New key pair: (32-byte seed, 32-byte public key x). The caller clears the seed after use.</summary>
        public static (byte[] Seed, byte[] PublicKey) Generate()
        {
            var gen = new Ed25519KeyPairGenerator();
            gen.Init(new Ed25519KeyGenerationParameters(new SecureRandom()));
            var kp = gen.GenerateKeyPair();
            var seed = ((Ed25519PrivateKeyParameters)kp.Private).GetEncoded();
            var x = ((Ed25519PublicKeyParameters)kp.Public).GetEncoded();
            return (seed, x);
        }

        public static byte[] PublicKeyFromSeed(byte[] seed)
        {
            if (seed is null || seed.Length != KeySize) throw new ArgumentException("Ed25519 seed must be 32 bytes", nameof(seed));
            return new Ed25519PrivateKeyParameters(seed, 0).GeneratePublicKey().GetEncoded();
        }

        public static byte[] Sign(byte[] seed, byte[] message)
        {
            if (seed is null || seed.Length != KeySize) throw new ArgumentException("Ed25519 seed must be 32 bytes", nameof(seed));
            var signer = new Ed25519Signer();
            signer.Init(true, new Ed25519PrivateKeyParameters(seed, 0));
            signer.BlockUpdate(message, 0, message.Length);
            return signer.GenerateSignature();
        }

        public static bool Verify(byte[] publicKey, byte[] message, byte[] signature)
        {
            if (publicKey is null || publicKey.Length != KeySize) return false;
            if (signature is null || signature.Length != SignatureSize) return false;
            if (message is null) return false;
            try
            {
                var verifier = new Ed25519Signer();
                verifier.Init(false, new Ed25519PublicKeyParameters(publicKey, 0));
                verifier.BlockUpdate(message, 0, message.Length);
                return verifier.VerifySignature(signature);
            }
            catch (ArgumentException)
            {
                return false;
            }
        }
    }
}
