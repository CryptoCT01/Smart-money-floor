/**
 * Shared Altana helpers for Smart Money Floor (BNB mainnet).
 * Never logs or returns private keys — only addresses + explorer URLs.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createPublicClient, http, formatEther } from "viem";
import { bsc } from "viem/chains";
import { generatePrivateKey } from "viem/accounts";
import {
  createClient,
  BNB,
  signerFromPrivateKey,
  serializeSession,
  deserializeSession,
} from "@altananetwork/sdk";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = resolve(__dirname, "../..");
export const ENV_PATH = resolve(ROOT, ".env.altana");
export const STATE_PATH = resolve(ROOT, ".altana-state.json");
export const SESSION_KEY_PATH = resolve(ROOT, ".altana-session.key");
export const SESSION_META_PATH = resolve(ROOT, ".altana-session.json");
/** Mainnet: no faucet — user sends BNB to the wallet address. */
export const EXPLORER_TX = "https://bscscan.com/tx/";
export const EXPLORER_ADDR = "https://bscscan.com/address/";
/** ~0.005 BNB / day spend cap */
export const SPEND_CAP_WEI = 5n * 10n ** 15n;
export const SESSION_TTL_SEC = 24 * 60 * 60;
/** Dust self-transfer for demo execute */
export const DEMO_TRANSFER_WEI = 10n ** 12n;
export const CHAIN_NAME = "BNB";
export const CHAIN_ID = BNB?.chainId || BNB?.chain?.id || 56;
export const DOCS_URL = "https://docs.altana.network/sdk/bnb";

export {
  createClient,
  BNB,
  signerFromPrivateKey,
  serializeSession,
  deserializeSession,
  generatePrivateKey,
};

export function loadEnvFile(path = ENV_PATH) {
  const out = {};
  if (!existsSync(path)) return out;
  for (const line of readFileSync(path, "utf8").split("\n")) {
    const t = line.trim();
    if (!t || t.startsWith("#")) continue;
    const i = t.indexOf("=");
    if (i < 0) continue;
    const k = t.slice(0, i).trim();
    let v = t.slice(i + 1).trim();
    if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) {
      v = v.slice(1, -1);
    }
    out[k] = v;
  }
  return out;
}

export function getAdminKey() {
  const env = { ...loadEnvFile(), ...process.env };
  const key = (env.ALTANA_ADMIN_KEY || env.PRIVATE_KEY || "").trim();
  if (!key || !key.startsWith("0x") || key.length < 66) {
    throw new Error("ALTANA_ADMIN_KEY missing/invalid in .env.altana");
  }
  return key;
}

export function readState() {
  if (!existsSync(STATE_PATH)) return null;
  try {
    return JSON.parse(readFileSync(STATE_PATH, "utf8"));
  } catch {
    return null;
  }
}

export function writeState(state) {
  const safe = { ...state };
  delete safe.adminKey;
  delete safe.privateKey;
  delete safe.sessionKey;
  writeFileSync(STATE_PATH, JSON.stringify(safe, null, 2) + "\n", { mode: 0o600 });
  return safe;
}

export function explorerTx(hash) {
  if (!hash) return null;
  return EXPLORER_TX + hash;
}

export function explorerAddr(addr) {
  if (!addr) return null;
  return EXPLORER_ADDR + addr;
}

export function makeClient() {
  return createClient({ chains: [BNB] });
}

export function makeAdmin() {
  return signerFromPrivateKey(getAdminKey());
}

export async function makeWallet(client = makeClient()) {
  const signer = makeAdmin();
  const wallet = await client.createWallet({ signer });
  return { client, signer, wallet };
}

export function publicRpc() {
  const rpc =
    (BNB && (BNB.publicRpcUrl || BNB.rpcUrl || BNB.rpc)) ||
    "https://bsc-dataseed.binance.org";
  return createPublicClient({
    chain: bsc,
    transport: http(typeof rpc === "string" ? rpc : "https://bsc-dataseed.binance.org"),
  });
}

export async function getNativeBalance(address) {
  const pc = publicRpc();
  const bal = await pc.getBalance({ address });
  return { wei: bal, ether: formatEther(bal), funded: bal > 0n };
}

export function saveSessionSecrets(sessionKeyHex, serialized) {
  writeFileSync(SESSION_KEY_PATH, sessionKeyHex.trim() + "\n", { mode: 0o600 });
  writeFileSync(SESSION_META_PATH, JSON.stringify(serialized, null, 2) + "\n", { mode: 0o600 });
}

export function loadSessionForExecute() {
  if (!existsSync(SESSION_KEY_PATH) || !existsSync(SESSION_META_PATH)) {
    throw new Error("No persisted session (.altana-session.key / .altana-session.json)");
  }
  const key = readFileSync(SESSION_KEY_PATH, "utf8").trim();
  const serialized = JSON.parse(readFileSync(SESSION_META_PATH, "utf8"));
  const session = deserializeSession(serialized, signerFromPrivateKey(key));
  return { session, serialized, publicKey: serialized.publicKey };
}

export function clearSessionSecrets() {
  for (const p of [SESSION_KEY_PATH, SESSION_META_PATH]) {
    if (existsSync(p)) writeFileSync(p, "", { mode: 0o600 });
  }
}

export function publicStatus() {
  const state = readState() || {};
  let hasSessionFiles = false;
  try {
    hasSessionFiles =
      existsSync(SESSION_KEY_PATH) &&
      existsSync(SESSION_META_PATH) &&
      readFileSync(SESSION_KEY_PATH, "utf8").trim().length > 0;
  } catch {
    hasSessionFiles = false;
  }
  const session = state.session || null;
  const awaitingFund = Boolean(state.walletAddress) && !state.funded;
  return {
    ok: true,
    chain: state.chain || CHAIN_NAME,
    chainId: state.chainId || CHAIN_ID,
    walletAddress: state.walletAddress || null,
    walletExplorer: state.walletAddress ? explorerAddr(state.walletAddress) : null,
    funded: Boolean(state.funded),
    balanceEther: state.balanceEther || null,
    fundHint: "Send BNB to address",
    session: session
      ? {
          active: Boolean(session.active) && hasSessionFiles && !session.revoked,
          publicKey: session.publicKey || null,
          expiry: session.expiry || null,
          expiryIso: session.expiry
            ? new Date(session.expiry * 1000).toISOString()
            : null,
          spendCapWei: session.spendCapWei || null,
          spendCapEther: session.spendCapEther || null,
          spendPeriod: session.spendPeriod || null,
          callsAllowlist: session.callsAllowlist || [],
          grantTxHash: session.grantTxHash || null,
          grantExplorer: session.grantExplorer || null,
          revoked: Boolean(session.revoked),
          revokeTxHash: session.revokeTxHash || null,
          revokeExplorer: session.revokeExplorer || null,
        }
      : null,
    lastTx: state.lastTx || null,
    waitForFund: awaitingFund,
    // legacy alias for older UI/server checks
    waitForFaucet: awaitingFund,
    docs: DOCS_URL,
  };
}
