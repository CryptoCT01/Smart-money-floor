/** One real on-chain tx through the session (self-transfer dust) on BNB mainnet */
import {
  makeClient,
  readState,
  writeState,
  getNativeBalance,
  loadSessionForExecute,
  explorerTx,
  explorerAddr,
  DEMO_TRANSFER_WEI,
} from "./lib.mjs";

async function main() {
  let state = readState();
  if (!state?.walletAddress) {
    console.log(JSON.stringify({ ok: false, error: "No wallet — run create-wallet first" }));
    process.exit(1);
  }
  const address = state.walletAddress;
  const bal = await getNativeBalance(address);
  state = writeState({
    ...state,
    funded: bal.funded,
    balanceEther: bal.ether,
    updatedAt: new Date().toISOString(),
  });

  if (!bal.funded) {
    console.log(JSON.stringify({
      ok: false,
      step: "execute-session",
      waitForFund: true,
      waitForFaucet: true,
      walletAddress: address,
      walletExplorer: explorerAddr(address),
      fundHint: "Send BNB to address",
      balanceEther: bal.ether,
      error: "Awaiting fund — send BNB to address, then re-run.",
    }, null, 2));
    process.exit(2);
  }

  if (!state.session?.active || state.session?.revoked) {
    console.log(JSON.stringify({
      ok: false,
      error: "No active session — run grant first",
      walletAddress: address,
    }));
    process.exit(1);
  }

  const { session } = loadSessionForExecute();
  const client = makeClient();
  const result = await client.execute({
    session,
    calls: [{ to: address, value: DEMO_TRANSFER_WEI }],
  });

  const txHash = result?.transactionHash || null;
  const lastTx = {
    kind: "session-self-transfer",
    status: result?.status || null,
    valueWei: DEMO_TRANSFER_WEI.toString(),
    to: address,
    hash: txHash,
    explorer: explorerTx(txHash),
    at: new Date().toISOString(),
  };
  writeState({ ...readState(), lastTx, updatedAt: new Date().toISOString() });

  console.log(JSON.stringify({
    ok: result?.status === "CONFIRMED" || result?.status === "PENDING",
    step: "execute-session",
    status: result?.status || null,
    walletAddress: address,
    lastTx,
  }, null, 2));

  if (result?.status === "FAILED") process.exit(1);
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e?.message || e) }));
  process.exit(1);
});
