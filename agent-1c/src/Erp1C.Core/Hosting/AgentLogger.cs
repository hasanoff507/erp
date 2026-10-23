using System.Collections.Generic;

namespace Erp1C.Core.Hosting
{
    /// <summary>
    /// Module logging seam (the agent maps it to Serilog + the A-06 log outbox, 34 §9). Messages are masked by the
    /// sink (34 §9.2); modules still never pass a secret or a full card number.
    /// </summary>
    public interface IAgentLogger
    {
        void Log(string level, string? code, string message, IReadOnlyDictionary<string, object?>? context = null);
    }

    public static class AgentLoggerExtensions
    {
        public static void Info(this IAgentLogger log, string? code, string message, IReadOnlyDictionary<string, object?>? context = null) =>
            log.Log("info", code, message, context);

        public static void Warn(this IAgentLogger log, string? code, string message, IReadOnlyDictionary<string, object?>? context = null) =>
            log.Log("warn", code, message, context);

        public static void Error(this IAgentLogger log, string? code, string message, IReadOnlyDictionary<string, object?>? context = null) =>
            log.Log("error", code, message, context);
    }

    public sealed class NullAgentLogger : IAgentLogger
    {
        public static readonly NullAgentLogger Instance = new NullAgentLogger();

        public void Log(string level, string? code, string message, IReadOnlyDictionary<string, object?>? context = null)
        {
        }
    }
}
