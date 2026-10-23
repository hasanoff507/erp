/** Do'kon agenti entity (33 §10.3 W-01/W-02; 34 §14.2 capabilities) — BO-14 and BO-12 bindings. */
export {
  $agents,
  $agentsError,
  $agentsLoaded,
  CAPABILITY_FAMILIES,
  agentName,
  agentUpdated,
  agentsFor,
  agentsRequested,
  deviceLabel,
  devicesOf,
  enabledFamilies,
  fetchAgentsFx,
  toAgent,
  toAgentList,
  type AgentCapability,
  type AgentDevice,
  type AgentStatus,
  type CapabilityFamily,
  type StoreAgent,
} from "./model/index.ts";
export { AgentDevicePicker, type AgentDeviceChoice } from "./ui/AgentDevicePicker.tsx";
