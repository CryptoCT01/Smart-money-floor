/** revokeSession via admin signer (BNB mainnet) */
import {
  makeWallet,
  readState,
  writeState,
  clearSessionSecrets,
  explorerTx,
  SESSION_META_PATH,
} from "./lib.mjs";
import { readFileSync, existsSync } from "node:fs";

async function main() {
  const state = readState();
  if (!state?.walletAddress) {
    console.log(JSON.stringify({ ok: false, error: "No wallet in state — run create-wallet first" }));
    process.exit(1);
  }
  const pub =
    state?.session?.publicKey ||
    (existsSync(SESSION_META_PATH)
      ? JSON.parse(readFileSync(SESSION_META_PATH, "utf8")).publicKey
      : null);
  if (!pub) {
    console.log(JSON.stringify({ ok: false, error: "No session public key to revoke" }));
    process.exit(1);
  }

  const { client, signer, wallet } = await makeWallet();
  const result = await client.revokeSession({
    wallet,
    signer,
    session: pub,
  });

  const revokeTxHash = result?.transactionHash || null;
  const prev = state.session || {};
  writeState({
    ...state,
    session: {
      ...prev,
      active: false,
      revoked: true,
      revokeTxHash,
      revokeExplorer: explorerTx(revokeTxHash),
      revokeStatus: result?.status || null,
    },
    updatedAt: new Date().toISOString(),
  });
  clearSessionSecrets();

  console.log(JSON.stringify({
    ok: result?.status !== "FAILED",
    step: "revoke-session",
    status: result?.status || null,
    walletAddress: state.walletAddress,
    sessionPublicKey: pub,
    revokeTxHash,
    revokeExplorer: explorerTx(revokeTxHash),
  }, null, 2));

  if (result?.status === "FAILED") process.exit(1);
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e?.message || e) }));
  process.exit(1);
});
