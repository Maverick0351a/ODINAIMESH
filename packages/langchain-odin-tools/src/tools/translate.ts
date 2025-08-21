import { RunnableLambda } from "@langchain/core/runnables";
import { OdinClient } from "odin-protocol-sdk";
import { z } from "zod";

export const TranslateInput = z.object({
  text: z.string(),
  from_sft: z.string().optional(),
  to_sft: z.string(),
});
export type TranslateInput = z.infer<typeof TranslateInput>;

export type TranslateToolConfig = {
  baseUrl: string;
  requireProof?: boolean;
};

export function makeTranslateTool(cfg: TranslateToolConfig) {
  let clientPromise: Promise<OdinClient> | null = null;
  const getClient = async () =>
    (clientPromise ??= OdinClient.fromDiscovery(cfg.baseUrl, {
      requireProof: cfg.requireProof ?? false,
    }));

  return RunnableLambda.from(async (input: TranslateInput) => {
    const client = await getClient();
    const req = {
      payload: { intent: "alpha@v1.hello", args: { text: input.text } },
      from_sft: input.from_sft ?? "alpha@v1",
      to_sft: input.to_sft,
    };
    const out = await client.postJson("/v1/translate", req);
    return out.payload;
  });
}
