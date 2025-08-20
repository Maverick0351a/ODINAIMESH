import { RunnableLambda } from "@langchain/core/runnables";
import { OdinClient } from "odin-protocol-sdk";

export type EchoToolConfig = {
  baseUrl: string;
  requireProof?: boolean;
};

export function makeEchoTool(cfg: EchoToolConfig) {
  let clientPromise: Promise<OdinClient> | null = null;
  const getClient = async () =>
    (clientPromise ??= OdinClient.fromDiscovery(cfg.baseUrl, {
      requireProof: cfg.requireProof ?? false,
    }));

  return RunnableLambda.from(async (input: unknown) => {
    const client = await getClient();
    const { echo } = await client.postJson("/v1/echo", { message: String(input ?? "") });
    return echo;
  });
}
