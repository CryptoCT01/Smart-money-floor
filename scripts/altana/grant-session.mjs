/** grantSession with call allowlist, spend cap, expiry; register:true (BNB mainnet) */
import { formatEther } from "viem";
import {
  makeWallet,
  readState,
  writeState,
  getNativeBalance,
  saveSessionSecrets,
  serializeSession,
  generatePrivateKey,
  signerFromPrivateKey,
  explorerTx,
  explorerAddr,
  SPEND_CAP_WEI,
  SESSION_TTL_SEC,
  CHAIN_NAME,
  CHAIN_ID,
} from "./lib.mjs";

async function main() {
  let state = readState();
  const { client, signer, wallet } = await makeWallet();
  const address = wallet.address;

  if (!state?.walletAddress) {
    state = writeState({
      chain: CHAIN_NAME,
      chainId: CHAIN_ID,
      walletAddress: address,
      walletExplorer: explorerAddr(address),
      createdAt: new Date().toISOString(),
      fundHint: "Send BNB to address",
    });
  }

  const bal = await getNativeBalance(address);
  state = writeState({
    ...state,
    walletAddress: address,
    walletExplorer: explorerAddr(address),
    funded: bal.funded,
    balanceEther: bal.ether,
    updatedAt: new Date().toISOString(),
  });

  if (!bal.funded) {
    console.log(JSON.stringify({
      ok: false,
      step: "grant-session",
      waitForFund: true,
      waitForFaucet: true,
      walletAddress: address,
      walletExplorer: explorerAddr(address),
      fundHint: "Send BNB to address",
      balanceEther: bal.ether,
      error: "Awaiting fund — send BNB to address, then re-run grant",
    }, null, 2));
    process.exit(2);
  }

  const sessionKey = generatePrivateKey();
  const sessionSigner = signerFromPrivateKey(sessionKey);
  const expiry = Math.floor(Date.now() / 1000) + SESSION_TTL_SEC;
  const permissions = {
    calls: [{ to: address }],
    spend: [{ limit: SPEND_CAP_WEI, period: "day" }],
  };

  const session = await client.grantSession({
    wallet,
    signer,
    sessionSigner,
    permissions,
    expiry,
    register: true,
  });

  const serialized = serializeSession(session);
  saveSessionSecrets(sessionKey, serialized);

  const grantTxHash = session.transactionHash || null;
  const sessionMeta = {
    active: true,
    revoked: false,
    publicKey: session.publicKey,
    expiry,
    spendCapWei: SPEND_CAP_WEI.toString(),
    spendCapEther: formatEther(SPEND_CAP_WEI),
    spendPeriod: "day",
    callsAllowlist: [address],
    grantTxHash,
    grantExplorer: explorerTx(grantTxHash),
    registered: true,
  };

  writeState({
    ...readState(),
    walletAddress: address,
    funded: true,
    balanceEther: bal.ether,
    session: sessionMeta,
    updatedAt: new Date().toISOString(),
  });

  console.log(JSON.stringify({
    ok: true,
    step: "grant-session",
    walletAddress: address,
    session: {
      publicKey: session.publicKey,
      expiry,
      expiryIso: new Date(expiry * 1000).toISOString(),
      spendCapEther: formatEther(SPEND_CAP_WEI),
      spendPeriod: "day",
      callsAllowlist: [address],
      register: true,
      grantTxHash,
      grantExplorer: explorerTx(grantTxHash),
    },
    next: "Run execute for a real session self-transfer, or revoke from UI",
  }, null, 2));
}

main().catch((e) => {
  console.error(JSON.stringify({ ok: false, error: String(e?.message || e) }));
  process.exit(1);
});
