const walletAddressEl = document.getElementById("wallet-address");
const walletBalanceEl = document.getElementById("wallet-balance");
const walletPublicEl = document.getElementById("wallet-public");
const walletPrivateEl = document.getElementById("wallet-private");
const nodeAliasInput = document.getElementById("node-alias");
const nodeAliasTag = document.getElementById("node-alias-tag");
const openAliasBtn = document.getElementById("open-alias-btn");
const statusDot = document.getElementById("node-status");
const importPrivEl = document.getElementById("import-priv");
const importSetActiveEl = document.getElementById("import-set-active");
const importModal = document.getElementById("import-modal");
const walletDetailModal = document.getElementById("wallet-detail-modal");
const detailAlias = document.getElementById("detail-alias");
const detailAddress = document.getElementById("detail-address");
const detailBalance = document.getElementById("detail-balance");
const detailPublic = document.getElementById("detail-public");
const detailPrivate = document.getElementById("detail-private");
const detailSetActiveBtn = document.getElementById("detail-set-active");
const detailCloseBtn = document.getElementById("detail-close");
const totalBalanceTag = document.getElementById("total-balance");
const aliasModal = document.getElementById("alias-modal");
const aliasSaveBtn = document.getElementById("alias-save-btn");
const aliasCancelBtn = document.getElementById("alias-cancel-btn");
if (importModal) importModal.hidden = true;
if (walletDetailModal) walletDetailModal.hidden = true;
const blocksEl = document.getElementById("blocks");
const blockCountEl = document.getElementById("block-count");
const blockSearchInput = document.getElementById("block-search");
const toastEl = document.getElementById("toast");
const newWalletBox = document.getElementById("new-wallet");
const newWalletAddress = document.getElementById("new-wallet-address");
const newWalletPub = document.getElementById("new-wallet-pub");
const newWalletPriv = document.getElementById("new-wallet-priv");
const feeDisplay = document.getElementById("fee-display");
const txAmountInput = document.getElementById("tx-amount");
const txRecipientInput = document.getElementById("tx-recipient");
const amountLabel = document.getElementById("amount-label");
const walletListEl = document.getElementById("wallet-list");
const autoMineToggle = document.getElementById("auto-mine-toggle");
const minerNameInput = document.getElementById("miner-name-input");
const minerAddressInput = document.getElementById("miner-address-input");
const saveConfigBtn = document.getElementById("save-config-btn");
const refreshConfigBtn = document.getElementById("refresh-config-btn");
const defaultWalletAddr = document.getElementById("default-wallet-addr");
const refreshIntervalInput = document.getElementById("refresh-interval-input");
const txAddressFilter = document.getElementById("tx-address-filter");
const txLimitInput = document.getElementById("tx-limit");
const txRefreshBtn = document.getElementById("tx-refresh");
const mempoolList = document.getElementById("mempool-list");
const confirmedList = document.getElementById("confirmed-list");
const mempoolCount = document.getElementById("mempool-count");
const confirmedCount = document.getElementById("confirmed-count");
const displayModeSelect = document.getElementById("display-mode");
let refreshIntervalSeconds = 0;
let refreshTimer = null;
const renameWalletModal = document.getElementById("rename-wallet-modal");
const renameWalletInput = document.getElementById("rename-wallet-input");
const renameWalletSave = document.getElementById("rename-wallet-save");
const renameWalletCancel = document.getElementById("rename-wallet-cancel");
let renameTargetAddress = null;
let coinName = "COIN";
let unitName = "unit";
let unitsPerCoin = 1;
let displayMode = "coin";
let lastWalletBalance = 0;
const copyTooltip = document.createElement("div");
copyTooltip.className = "copy-tooltip";
copyTooltip.textContent = "Copied!";
copyTooltip.style.position = "fixed";
copyTooltip.style.padding = "6px 10px";
copyTooltip.style.background = "#0f172a";
copyTooltip.style.border = "1px solid #1f2937";
copyTooltip.style.borderRadius = "8px";
copyTooltip.style.color = "#fff";
copyTooltip.style.fontSize = "12px";
copyTooltip.style.pointerEvents = "none";
copyTooltip.style.zIndex = "9999";
copyTooltip.style.display = "none";
document.body.appendChild(copyTooltip);

// Normalize and de-duplicate wallets aggressively (trim address, enforce uniqueness)
function normalizeWalletEntry(entry) {
  if (!entry) return null;
  const address = (entry.address || "").trim().toLowerCase();
  if (!address) return null;
  return {
    alias: entry.alias || "Wallet",
    address, // normalized lowercase to avoid duplicates by casing
    public_key: entry.public_key || "",
    private_key: entry.private_key || "",
  };
}
let cachedChain = [];

async function fetchJson(url, opts = {}) {
  const res = await fetch(url, { headers: { "Content-Type": "application/json" }, ...opts });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json();
}

function showToast(msg, type = "") {
  toastEl.textContent = msg;
  toastEl.className = `toast ${type}`;
  toastEl.hidden = false;
  setTimeout(() => (toastEl.hidden = true), 3000);
}

async function loadWallet() {
  try {
    const data = await fetchJson("/wallet/info");
    if (walletAddressEl) walletAddressEl.textContent = data.address ?? data.addres ?? "-";
    lastWalletBalance = data.balance ?? 0;
    if (walletBalanceEl) walletBalanceEl.textContent = formatAmount(lastWalletBalance);
    if (walletPublicEl) walletPublicEl.textContent = data.public_key ?? "-";
    if (walletPrivateEl) {
      walletPrivateEl.textContent = data.private_key ?? "-";
      walletPrivateEl.classList.remove("revealed");
    }
    applyAlias();
    setOnlineStatus(true);
    const existing = getStoredWallets().some((w) => w.address === data.address);
    if (!existing) {
      upsertStoredWallet(data, "Node wallet");
    }
    cleanWalletStorage();
    debugLogWallets("after loadWallet");
    renderWalletList();
  } catch (err) {
    setOnlineStatus(false);
    showToast(err.message, "error");
  }
}

function renderBlocks(chain) {
  if (!blocksEl || !blockCountEl) return;
  cachedChain = chain;
  blockCountEl.textContent = `${chain.length} blocks`;
  blocksEl.innerHTML = "";
  const query = (blockSearchInput?.value || "").toLowerCase();
  const filtered = [...chain].filter((block) => {
    if (!query) return true;
    const matchBlock = block.hash?.toLowerCase().includes(query);
    const matchTx = (block.data || []).some((tx) => {
      const txIdMatch = (tx.id || "").toLowerCase().includes(query);
      const inputAddrMatch = ((tx.input?.address) || "").toLowerCase().includes(query);
      const outputAddrMatch = Object.keys(tx.output || {}).some((addr) =>
        addr.toLowerCase().includes(query)
      );
      return txIdMatch || inputAddrMatch || outputAddrMatch;
    });
    return matchBlock || matchTx;
  }).reverse();

  filtered.forEach((block, idxFiltered) => {
    const div = document.createElement("div");
    div.className = "block";
    const height = chain.length - 1 - idxFiltered;
    div.innerHTML = `
      <div class="block-top">
        <div>
          <div class="tag">Height ${height}</div>
          <p class="mono" style="margin:4px 0 0;"><a class="addr-link" href="/block/${block.hash}">${block.hash}</a></p>
        </div>
        <small class="muted">Txs: ${block.data.length}</small>
      </div>
    `;
    block.data.forEach((tx) => {
      const txDiv = document.createElement("div");
      txDiv.className = "tx";
      const isReward = JSON.stringify(tx.input) === JSON.stringify({ address: "+--official-mining-reward--+" });
      txDiv.innerHTML = `
        <div class="tx-header">
          <span class="mono">tx: ${tx.id || "n/a"}</span>
          <small>${isReward ? "Reward" : "Transfer"}</small>
        </div>
        <small>From: ${isReward ? (tx.input?.address ?? "genesis") : `<a class="addr-link" href="/address/${tx.input?.address}">${tx.input?.address ?? "genesis"}</a>`} | Fee: ${formatAmountWithSecondary(tx.input?.fee ?? 0)}</small>
        <div class="mono">Outputs:</div>
      `;
      const outputsList = document.createElement("ul");
      Object.entries(tx.output || {}).forEach(([addr, val]) => {
        const li = document.createElement("li");
        if (isReward) {
          li.innerHTML = `<span class="addr-link disabled">${addr}</span>: ${formatAmountWithSecondary(val)}`;
        } else {
          li.innerHTML = `<a class="addr-link" href="/address/${addr}">${addr}</a>: ${formatAmountWithSecondary(val)}`;
        }
        outputsList.appendChild(li);
      });
      txDiv.appendChild(outputsList);
      div.appendChild(txDiv);
    });
    blocksEl.appendChild(div);
  });
}

async function loadChain() {
  try {
    const chain = await fetchJson("/blockchain");
    renderBlocks(chain);
  } catch (err) {
    showToast(err.message, "error");
  }
}

function renderTxList(list, targetEl, statusLabel = "", chainHeight = null) {
  if (!targetEl) return;
  if (!list || list.length === 0) {
    targetEl.innerHTML = `<p class="muted">No ${statusLabel || "transactions"} found.</p>`;
    return;
  }

  const rows = list.map((tx) => {
    const totalOut = Object.values(tx.output || {}).reduce((a, b) => a + Number(b || 0), 0);
    const feeText = formatAmountWithSecondary(tx.fee || 0);
    const amountText = formatAmountWithSecondary(totalOut);
    const statusTag = tx.status === "mempool" ? "Pending" : "Confirmed";
    const blockInfo = tx.status === "confirmed"
      ? `<small>Height ${tx.height} | Block ${tx.block_hash?.slice(0, 12) ?? "n/a"}</small>`
      : `<small>Awaiting inclusion</small>`;
    const confirmations = tx.status === "confirmed" && chainHeight !== null ? Math.max(0, chainHeight - (tx.height || 0)) : 0;
    const confText = tx.status === "confirmed" ? ` | Confirmations: ${confirmations}` : "";
    const outputs = Object.entries(tx.output || {}).map(([addr, val]) => `<li><span class="mono">${addr}</span>: ${formatAmountWithSecondary(val)}</li>`).join("");
    return `
      <div class="tx-card">
        <header class="tx-card__header">
          <div>
            <div class="mono">tx: ${tx.id || "n/a"}</div>
            ${blockInfo}${confText}
          </div>
          <span class="tag ${tx.status === "mempool" ? "warning" : "success"}">${statusTag}</span>
        </header>
        <div class="tx-card__meta">
          <span>Amount: ${amountText}</span>
          <span>Fee: ${feeText}</span>
        </div>
        <div class="tx-card__outputs">
          <div class="label">Outputs</div>
          <ul>${outputs || "<li class='muted'>No outputs</li>"}</ul>
        </div>
      </div>
    `;
  });

  targetEl.innerHTML = rows.join("");
}

async function loadTransactionsFeed() {
  if (!mempoolList || !confirmedList) return;
  const params = new URLSearchParams();
  const address = (txAddressFilter?.value || "").trim();
  const limit = Number(txLimitInput?.value || 50);
  if (address) params.set("address", address);
  if (limit) params.set("limit", limit);

  try {
    const data = await fetchJson(`/transactions/feed?${params.toString()}`);
    renderTxList(data.mempool || [], mempoolList, "mempool", data.height);
    renderTxList(data.confirmed || [], confirmedList, "confirmed", data.height);
    if (mempoolCount) mempoolCount.textContent = `${(data.mempool || []).length} pending`;
    if (confirmedCount) confirmedCount.textContent = `${(data.confirmed || []).length} recent`;
  } catch (err) {
    showToast(`Tx feed error: ${err.message}`, "error");
  }
}

async function loadConfig() {
  try {
    const cfg = await fetchJson("/config");
    if (autoMineToggle) autoMineToggle.checked = !!cfg.auto_mine;
    if (minerNameInput) minerNameInput.value = cfg.miner_name || "";
    if (minerAddressInput) minerAddressInput.value = cfg.miner_address || "";
    if (defaultWalletAddr) defaultWalletAddr.textContent = cfg.default_wallet_address || "-";
    if (refreshIntervalInput) refreshIntervalInput.value = cfg.refresh_interval_seconds ?? 0;
    refreshIntervalSeconds = cfg.refresh_interval_seconds ?? 0;
    coinName = cfg.coin_name || coinName;
    unitName = cfg.unit_name || unitName;
    unitsPerCoin = cfg.units_per_coin || unitsPerCoin;
    updateDisplayModeOptions();
    refreshAmountDisplays();
    applyAutoRefresh();
  } catch (err) {
    showToast(`Config error: ${err.message}`, "error");
  }
}

async function saveConfig() {
  try {
    const body = {
      auto_mine: autoMineToggle?.checked || false,
      miner_name: minerNameInput?.value || "",
      miner_address: minerAddressInput?.value || "",
      refresh_interval_seconds: Number(refreshIntervalInput?.value ?? refreshIntervalSeconds),
    };
    await fetchJson("/config", { method: "POST", body: JSON.stringify(body) });
    showToast("Config saved", "success");
    refreshIntervalSeconds = body.refresh_interval_seconds || 0;
    applyAutoRefresh();
  } catch (err) {
    showToast(err.message, "error");
  }
}

document.getElementById("refresh-btn")?.addEventListener("click", () => {
  loadWallet();
  loadChain();
});

saveConfigBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  saveConfig();
});
autoMineToggle?.addEventListener("change", () => saveConfig());
refreshConfigBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  loadConfig();
});
refreshIntervalInput?.addEventListener("change", () => saveConfig());
displayModeSelect?.addEventListener("change", () => {
  displayMode = displayModeSelect.value || "coin";
  refreshAmountDisplays();
});

blockSearchInput?.addEventListener("input", () => {
  renderBlocks(cachedChain);
});

document.getElementById("mine-btn")?.addEventListener("click", async () => {
  try {
    await fetchJson("/blockchain/mine");
    showToast("Block mined", "success");
    loadWallet();
    loadChain();
  } catch (err) {
    showToast(err.message, "error");
  }
});

document.getElementById("create-wallet-btn")?.addEventListener("click", async () => {
  try {
    const w = await fetchJson("/wallet/create", { method: "POST" });
    newWalletBox.hidden = false;
    newWalletAddress.textContent = w.address;
    newWalletPub.textContent = w.public_key;
    newWalletPriv.textContent = w.private_key;
    newWalletPriv.classList.remove("revealed");
    newWalletPriv.classList.remove("muted");
    showToast("Wallet created", "success");
    upsertStoredWallet(w, "New wallet");
    cleanWalletStorage();
    renderWalletList();
  } catch (err) {
    showToast(err.message, "error");
  }
});

document.getElementById("tx-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const recipient = txRecipientInput.value.trim();
  const amountUnits = getInputAmountUnits();
  if (!recipient || amountUnits <= 0) {
    showToast("Invalid data", "error");
    return;
  }
  try {
    const pendingTx = await fetchJson("/wallet/transact", {
      method: "POST",
      body: JSON.stringify({ recipient, amount: amountUnits })
    });
    const fee = pendingTx.input?.fee ?? 0;
    showToast(`Transaction sent. Fee: ${formatAmountWithSecondary(fee)}`, "success");
    loadWallet();
    loadChain();
  } catch (err) {
    showToast(err.message, "error");
  }
});

txAmountInput?.addEventListener("input", updateEstimatedFee);
txRecipientInput?.addEventListener("input", updateEstimatedFee);
txRefreshBtn?.addEventListener("click", () => loadTransactionsFeed());
txAddressFilter?.addEventListener("change", () => loadTransactionsFeed());
txLimitInput?.addEventListener("change", () => loadTransactionsFeed());

// init
updateDisplayModeOptions();
cleanWalletStorage();
loadWallet();
loadChain();
loadTransactionsFeed();
loadConfig();
if (importModal) importModal.hidden = true;
if (walletDetailModal) walletDetailModal.hidden = true;
newWalletPriv?.addEventListener("click", () => {
  newWalletPriv.classList.toggle("revealed");
});
walletPrivateEl?.addEventListener("click", () => {
  walletPrivateEl.classList.toggle("revealed");
});
applyAlias();
renderWalletList();
if (renameWalletModal) renameWalletModal.hidden = true;
attachCopyOnHover(".mono, .addr-link, #wallet-private, #wallet-public, #wallet-address, #detail-address, #detail-public, #detail-private");

async function importWallet({ private_key, set_active, alias }) {
  const w = await fetchJson("/wallet/import", {
    method: "POST",
    body: JSON.stringify({ private_key, set_active })
  });
  showToast(set_active ? "Wallet imported and set active" : "Wallet imported", "success");
  return w;
}

function getStoredWallets() {
  try {
    const list = JSON.parse(localStorage.getItem("wallets") || "[]");
    return uniqueByAddress(list);
  } catch {
    return [];
  }
}

function setStoredWallets(w) {
  localStorage.setItem("wallets", JSON.stringify(uniqueByAddress(w)));
}

function renameStoredWallet(address, alias) {
  const wallets = getStoredWallets();
  const idx = wallets.findIndex((w) => w.address === address);
  if (idx >= 0) {
    wallets[idx].alias = alias;
    setStoredWallets(wallets);
  }
}

function openRenameModal(address, currentAlias = "") {
  renameTargetAddress = address;
  if (renameWalletInput) {
    renameWalletInput.value = currentAlias;
    renameWalletInput.focus();
  }
  if (renameWalletModal) renameWalletModal.hidden = false;
}

function closeRenameModal() {
  renameTargetAddress = null;
  if (renameWalletModal) renameWalletModal.hidden = true;
}

function attachCopyOnHover(selector) {
  const elems = document.querySelectorAll(selector);
  elems.forEach((el) => {
    el.style.cursor = "pointer";
    el.title = "Click to copy";
    el.addEventListener("click", async (e) => {
      e.stopPropagation();
      const text = el.textContent?.trim() || "";
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        showCopyTooltip(e.clientX, e.clientY);
      } catch {
        showToast("Copy failed", "error");
      }
    });
  });
}

function showCopyTooltip(x, y) {
  if (!copyTooltip) return;
  copyTooltip.style.left = `${x + 8}px`;
  copyTooltip.style.top = `${y + 8}px`;
  copyTooltip.style.display = "block";
  setTimeout(() => {
    copyTooltip.style.display = "none";
  }, 800);
}

function upsertStoredWallet(wallet, alias) {
  const wallets = uniqueByAddress(getStoredWallets());
  const entry = normalizeWalletEntry({
    alias: alias || wallet.alias || "Wallet",
    address: wallet.address,
    public_key: wallet.public_key,
    private_key: wallet.private_key,
  });
  if (!entry) return;
  console.log("[wallets] upsert wallet", entry.address, "alias", entry.alias);
  const existingIdx = wallets.findIndex((w) => w.address === entry.address);
  if (existingIdx >= 0) {
    wallets[existingIdx] = entry;
  } else {
    wallets.push(entry);
  }
  setStoredWallets(wallets);
}

function uniqueByAddress(list) {
  const unique = {};
  list.forEach((w) => {
    const normalized = normalizeWalletEntry(w);
    if (normalized) unique[normalized.address] = normalized;
  });
  return Object.values(unique);
}

function debugLogWallets(reason) {
  try {
    const raw = localStorage.getItem("wallets") || "[]";
    const parsed = JSON.parse(raw);
    const cleaned = uniqueByAddress(Array.isArray(parsed) ? parsed : []);
    console.log(`[wallets] ${reason}`, {
      rawCount: Array.isArray(parsed) ? parsed.length : "n/a",
      cleanedCount: cleaned.length,
      addresses: cleaned.map((w) => w.address),
    });
  } catch (e) {
    console.log("[wallets] debug failed", e);
  }
}

function cleanWalletStorage() {
  const cleaned = uniqueByAddress(getStoredWallets());
  setStoredWallets(cleaned);
  return cleaned;
}

let renderWalletListCurrent = null;
async function renderWalletList() {
  if (!walletListEl || !totalBalanceTag) return;
  if (renderWalletListCurrent) {
    return renderWalletListCurrent;
  }

  renderWalletListCurrent = (async () => {
    const wallets = cleanWalletStorage();
    debugLogWallets("renderWalletList cleaned");
    const rendered = new Set();
    const items = [];
    let total = 0;

    for (const w of wallets) {
      if (!w || !w.address || rendered.has(w.address)) continue;
      rendered.add(w.address);
      console.log("[wallets] rendering entry", w);
      const balance = await fetchWalletBalance(w.address);
      total += balance;
      items.push({
        address: w.address,
        alias: w.alias || "Wallet",
        balance,
        public_key: w.public_key,
        private_key: w.private_key,
      });
    }

    // Render in one go to avoid interleaved concurrent renders
    walletListEl.innerHTML = items
      .map(
        (item) => `
      <div class="wallet-item">
        <header>
          <div>
            <strong>${item.alias}</strong>
            <div class="mono">${item.address}</div>
          </div>
        <div class="actions">
            <span class="tag">Balance: ${formatAmount(item.balance)}</span>
            <button class="ghost set-active" data-address="${item.address}" data-has-key="true">Set active</button>
            <button class="ghost edit" data-address="${item.address}" data-alias="${item.alias}">Rename</button>
            <button class="ghost danger delete" data-address="${item.address}">Delete</button>
          </div>
        </header>
        <small>Tap to view keys</small>
      </div>`
      )
      .join("");

    // Attach handlers
    Array.from(walletListEl.querySelectorAll(".wallet-item")).forEach((el, idx) => {
      const item = items[idx];
      el.addEventListener("click", () => openWalletDetail(item, item.balance));
    });

    walletListEl.querySelectorAll(".set-active").forEach((btn) => {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const addr = btn.getAttribute("data-address");
        const wallets = getStoredWallets();
        const target = wallets.find((w) => w.address === addr);
        if (!target) return;
        try {
          await importWallet({ private_key: target.private_key, set_active: true, alias: target.alias });
          showToast("Node wallet changed", "success");
          loadWallet();
        } catch (err) {
          showToast(err.message, "error");
        }
      });
    });

    walletListEl.querySelectorAll(".delete").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const addr = btn.getAttribute("data-address");
      const wallets = getStoredWallets().filter((w) => w.address !== addr);
      setStoredWallets(wallets);
      renderWalletList();
    });
  });
    walletListEl.querySelectorAll(".edit").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        const addr = btn.getAttribute("data-address");
        const alias = btn.getAttribute("data-alias") || "Wallet";
        openRenameModal(addr, alias);
      });
    });

    totalBalanceTag.textContent = `Total: ${formatAmount(total)}`;
    console.log("[wallets] DOM after render", walletListEl.children.length, Array.from(walletListEl.querySelectorAll(".wallet-item .mono")).map((n) => n.textContent));
  })();

  try {
    await renderWalletListCurrent;
  } finally {
    renderWalletListCurrent = null;
  }
}

async function fetchWalletBalance(address) {
  try {
    const res = await fetchJson(`/wallet/balance?address=${address}`);
    return res.balance ?? 0;
  } catch {
    return 0;
  }
}

function openWalletDetail(wallet, balance) {
  if (!walletDetailModal) return;
  detailAlias.textContent = wallet.alias || "Wallet detail";
  detailAddress.textContent = wallet.address;
  detailBalance.textContent = formatAmountWithSecondary(balance);
  detailPublic.textContent = wallet.public_key;
  detailPrivate.textContent = wallet.private_key || "Not stored for this entry";
  if (wallet.private_key) {
    detailPrivate.classList.remove("revealed");
    detailSetActiveBtn && (detailSetActiveBtn.disabled = false);
  } else {
    detailPrivate.classList.add("muted");
    detailSetActiveBtn && (detailSetActiveBtn.disabled = true);
  }
  if (detailSetActiveBtn) {
    detailSetActiveBtn.onclick = async () => {
      try {
        await importWallet({ private_key: wallet.private_key, set_active: true, alias: wallet.alias });
        showToast("Node wallet changed", "success");
        loadWallet();
      } catch (err) {
        showToast(err.message, "error");
      }
    };
  }
  walletDetailModal.hidden = false;
}
function applyAlias() {
  if (!nodeAliasTag) return;
  const alias = localStorage.getItem("node_alias") || "Unnamed";
  if (nodeAliasInput) nodeAliasInput.value = alias === "Unnamed" ? "" : alias;
  nodeAliasTag.textContent = alias;
}
aliasSaveBtn?.addEventListener("click", () => {
  const val = (nodeAliasInput?.value.trim() || "Unnamed");
  localStorage.setItem("node_alias", val);
  applyAlias();
  if (aliasModal) aliasModal.hidden = true;
});
aliasCancelBtn?.addEventListener("click", () => {
  if (aliasModal) aliasModal.hidden = true;
});
openAliasBtn?.addEventListener("click", () => {
  if (aliasModal) {
    aliasModal.hidden = false;
    if (nodeAliasInput) {
      nodeAliasInput.value = localStorage.getItem("node_alias") || "";
    }
  }
});

document.getElementById("import-confirm-btn")?.addEventListener("click", async () => {
  const priv = importPrivEl.value.trim();
  const setActive = importSetActiveEl.checked;
  if (!priv) {
    showToast("Private key required", "error");
    return;
  }
  try {
    const alias = nodeAliasInput.value.trim() || "Imported wallet";
    const w = await importWallet({ private_key: priv, set_active: setActive, alias });
    upsertStoredWallet({ ...w, private_key: priv }, alias);
    cleanWalletStorage();
    renderWalletList();
    loadWallet();
    if (importModal) importModal.hidden = true;
  } catch (err) {
    showToast(err.message, "error");
  }
});

document.getElementById("import-cancel-btn").addEventListener("click", () => {
  if (importModal) importModal.hidden = true;
});

detailCloseBtn?.addEventListener("click", () => {
  if (walletDetailModal) walletDetailModal.hidden = true;
});

detailPrivate?.addEventListener("click", () => {
  detailPrivate.classList.toggle("revealed");
});

renameWalletCancel?.addEventListener("click", () => {
  closeRenameModal();
});
renameWalletSave?.addEventListener("click", () => {
  const newAlias = renameWalletInput?.value.trim() || "";
  if (renameTargetAddress && newAlias) {
    renameStoredWallet(renameTargetAddress, newAlias);
    renderWalletList();
  }
  closeRenameModal();
});

function setOnlineStatus(isOnline) {
  if (!statusDot) return;
  if (isOnline) {
    statusDot.classList.add("online");
  } else {
    statusDot.classList.remove("online");
  }
}

function toCoinValue(units) {
  const u = Number(units) || 0;
  if (!unitsPerCoin || unitsPerCoin <= 1) return u;
  return u / unitsPerCoin;
}

function formatCoinAmount(units) {
  const coinValue = toCoinValue(units);
  const formatted = coinValue.toFixed(8).replace(/\.?0+$/, "");
  return `${formatted} ${coinName}`;
}

function formatUnitAmount(units) {
  const u = Number(units) || 0;
  return `${u.toLocaleString()} ${unitName}`;
}

function formatAmount(units) {
  return displayMode === "unit" ? formatUnitAmount(units) : formatCoinAmount(units);
}

function formatAmountSecondary(units) {
  return displayMode === "unit" ? formatCoinAmount(units) : formatUnitAmount(units);
}

function formatAmountWithSecondary(units) {
  return `${formatAmount(units)} (${formatAmountSecondary(units)})`;
}

function refreshAmountDisplays() {
  loadWallet();
  renderBlocks(cachedChain);
  renderWalletList();
  updateEstimatedFee();
  updateAmountLabel();
}

function updateDisplayModeOptions() {
  if (!displayModeSelect) return;
  const coinOpt = displayModeSelect.querySelector('option[value="coin"]');
  const unitOpt = displayModeSelect.querySelector('option[value="unit"]');
  if (coinOpt) coinOpt.textContent = coinName;
  if (unitOpt) unitOpt.textContent = unitName;
  displayModeSelect.value = displayMode;
}

function updateAmountLabel() {
  if (!amountLabel) return;
  const unitLabel = displayMode === "unit" ? unitName : coinName;
  amountLabel.textContent = `Amount (${unitLabel})`;
}

function getInputAmountUnits() {
  const raw = Number(txAmountInput?.value || 0);
  if (!unitsPerCoin || unitsPerCoin <= 1) return raw;
  return displayMode === "unit" ? raw : raw * unitsPerCoin;
}

async function updateEstimatedFee() {
  if (!feeDisplay) return;
  const amountUnits = getInputAmountUnits();
  const recipient = txRecipientInput?.value || "";
  if (!recipient || amountUnits <= 0) {
    feeDisplay.textContent = "Fee: -";
    return;
  }
  try {
    const res = await fetchJson(`/wallet/estimate_fee?amount=${amountUnits}&recipient=${encodeURIComponent(recipient)}`);
    const fee = res.fee ?? 0;
    const total = res.total_required ?? amountUnits + fee;
    const balance = res.balance ?? 0;
    const suff = total <= balance ? "" : " (exceeds balance)";
    const feeText = formatAmountWithSecondary(fee);
    const totalText = formatAmountWithSecondary(total);
    feeDisplay.textContent = `Fee: ${feeText} | Total: ${totalText}${suff}`;
  } catch {
    feeDisplay.textContent = "Fee: n/a";
  }
}

function applyAutoRefresh() {
  if (refreshTimer) {
    clearInterval(refreshTimer);
    refreshTimer = null;
  }
  const canAutoRefresh = !!blocksEl;
  if (!canAutoRefresh) return;
  if (!refreshIntervalSeconds || refreshIntervalSeconds <= 0) return;
  refreshTimer = setInterval(() => {
    loadChain();
    loadWallet();
  }, refreshIntervalSeconds * 1000);
}
