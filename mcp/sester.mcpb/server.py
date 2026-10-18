#!/usr/bin/env python3
"""SESTER MCP server — AI ajanları için ödeme-kanıtı araçları.

Model Context Protocol 2025-06-18 (JSON-RPC 2.0 over stdio), saf-stdlib:
  - `initialize` → protocolVersion 2025-06-18 + tools capability
  - `notifications/initialized`
  - `tools/list`, `tools/call`

Araçlar:
  pay(agent, resource, amount, ...)        → ücretlendir + node-cosigned receipt
  verify_receipt(receipt_json)             → alıcı-tarafı bağımsız doğrulama
  balance(agent)                           → günlük harcama / kota / kalan
  history(agent?, limit?)                  → kanıt-zinciri olayları

Modlar:
  embedded (varsayılan)  — bu süreçteki ledger; $0, testnet/mainnet YOK
  remote (SESTER_MCP_ENDPOINT) — gerçek bir Sester-korumalı API'ye x402 ödemesi

Çevre-değişkenleri:
  SESTER_MCP_DB        ledger yolu (varsayılan: sester-mcp.sqlite3)
  SESTER_MCP_SECRET    ledger-mührü (ZORUNLU — üretimde set-edin)
  SESTER_MCP_NODE_SECRET  node-cosign anahtarı (yoksa receipt cosign'siz)
  SESTER_MCP_NODE_ID   node kimliği (varsayılan: sester:mcp-node)
  SESTER_MCP_QUOTA     ajan-başına günlük kota (varsayılan: 5.00)
  SESTER_MCP_ENDPOINT  remote mod URL'si (örn. http://127.0.0.1:8402)

Smithery/Arcade ile yayınlanabilir (bkz. mcp/smithery.yaml).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

# Geliştirme-modu path çözümü: pip-install-edilmemişse, repo-kökünden `sester`
# bulunur (Smithery `startCommand` bu dosyayı çalıştırır; dağıtımda sester
# kuruludur ve bu aramanın hiçbir maliyeti yoktur).
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

PROTOCOL_VERSION = "2025-06-18"
SERVER_NAME = "sester"

_DB = os.environ.get("SESTER_MCP_DB", "sester-mcp.sqlite3")
_SECRET = os.environ.get("SESTER_MCP_SECRET", "")
_NODE_SECRET = os.environ.get("SESTER_MCP_NODE_SECRET", "")
_NODE_ID = os.environ.get("SESTER_MCP_NODE_ID", "sester:mcp-node")
_QUOTA = float(os.environ.get("SESTER_MCP_QUOTA", "5.00"))
_ENDPOINT = os.environ.get("SESTER_MCP_ENDPOINT", "").rstrip("/")
_CURRENCY = os.environ.get("SESTER_MCP_CURRENCY", "USDC-sim")

_ledger: Any = None


def _warn(msg: str) -> None:
    print(f"SESTER-MCP UYARI: {msg}", file=sys.stderr, flush=True)


_LED: Any = None


def _ledger():
    """Embedded ledger (geç başlatma — import-anında side-effect yok)."""
    global _LED
    if _LED is not None:
        return _LED
    from sester.ledger import Ledger
    secret = _SECRET
    if not secret:
        # demo-değer uyarı-ama-çalışır (üretim-değil) — fail-closed değil çünkü
        # MCP server'ın local denemede ayakta olması gerek; sessiz DEĞİL.
        _warn("SESTER_MCP_SECRET set-değil — demo-secret kullanılıyor "
              "(üretimde set-edin)")
        secret = "sester-mcp-demo-secret"
    _LED = Ledger(_DB, secret=secret)
    return _LED


def _tool_result(text: str, is_error: bool = False) -> dict[str, Any]:
    """MCP tools/call yanıtı (2025-06-18: content[].text + isError)."""
    return {"content": [{"type": "text", "text": text}],
            "isError": is_error}


def _json_out(obj: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _err(code: int, message: str, rid: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rid,
            "error": {"code": code, "message": message}}


# ---------------- araçlar ----------------

def tool_pay(args: dict[str, Any]) -> dict[str, Any]:
    """Bir ajan adına ödeme yap → node-cosigned receipt.
    Embedded mod: lokal ledger'a charge_receipt yazar (anahtar YOK, $0).
    Remote mod: SESTER_MCP_ENDPOINT'e x402 ödeme yapar (gerçek zincir)."""
    from sester.receipt import issue_receipt, receipt_json

    agent = str(args.get("agent", "")).strip()
    resource = str(args.get("resource", "/")).strip()
    amount = float(args.get("amount", 0))
    if not agent:
        return _tool_result("hata: 'agent' zorunlu", is_error=True)
    if amount <= 0:
        return _tool_result(f"hata: amount>0 gerekli (alinan={amount})",
                            is_error=True)
    amount_minor = int(round(amount * 1_000_000))
    if _ENDPOINT:
        return _pay_remote(agent, resource, amount, amount_minor)
    led = _ledger()
    spent = led.spent_today_minor(agent) if hasattr(led, "spent_today_minor") \
        else int(round(led.spent_today(agent) * 1_000_000))
    if spent + amount_minor > int(round(_QUOTA * 1_000_000)):
        return _tool_result(
            f"quota_exceeded: agent={agent} spent_today={spent / 1_000_000:.6f}"
            f" daily_quota={_QUOTA:.2f} — pay kaldırıldı (fail-closed)",
            is_error=True)
    ev = led.append("charge_receipt", agent, resource, amount,
                    amount_minor=amount_minor,
                    payload={"nonce": os.urandom(8).hex(),
                             "paid": amount, "scheme": "sester-mcp"})
    r = issue_receipt(
        ev, node_id=_NODE_ID,
        node_secret=_NODE_SECRET.encode() if _NODE_SECRET else None,
        chain_head=led.chain_head(), currency=_CURRENCY)
    return _tool_result(
        receipt_json(r) + f"\n# kanıt: sester verify receipt.json  (seq={r['seq']})")


def _pay_remote(agent: str, resource: str, amount: float,
                amount_minor: int) -> dict[str, Any]:
    """Remote mod: gerçek Sester API'sine x402 HMAC ödemesi (gerçek zincir).
    Demo-secret yerine sunucu-secret'ı bilinmelidir (SESTER_MCP_REMOTE_SECRET)."""
    if resource.startswith("http"):
        url = resource
    else:
        url = _ENDPOINT + resource
    nonce = os.urandom(8).hex()
    secret = os.environ.get("SESTER_MCP_REMOTE_SECRET", _SECRET)
    if not secret:
        return _tool_result("hata: remote mod için SESTER_MCP_REMOTE_SECRET "
                            "gerekli", is_error=True)
    mac = hmac.new(secret.encode(),
                   f"{agent}|{nonce}|{amount:.6f}|{resource}".encode(),
                   hashlib.sha256).hexdigest()
    payment = f"pugio0 {agent}:{nonce}:{amount:.6f}:{mac}"
    req = urllib.request.Request(url)
    req.add_header("X-Payment", payment)
    req.add_header("X-Sester-Agent", agent)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode("utf-8", "replace")
            receipt_hash = resp.headers.get("x-sester-receipt")
            return _tool_result(
                f"status={resp.status} receipt={receipt_hash}\n"
                f"# body: {body[:400]}")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        return _tool_result(f"remote-payment RED: HTTP {e.code} — {detail}",
                            is_error=True)
    except Exception as e:  # ağ/DNS — fail-closed raporu
        return _tool_result(f"remote-payment hatası: {e}", is_error=True)


def tool_verify_receipt(args: dict[str, Any]) -> dict[str, Any]:
    """Receipt'i bağımsız doğrula (alıcı tarafı — Sester gerektirmez)."""
    from sester.receipt import load_receipt_json, verify_receipt

    raw = args.get("receipt")
    if not raw:
        return _tool_result("hata: 'receipt' (JSON) zorunlu", is_error=True)
    try:
        r = load_receipt_json(raw if isinstance(raw, str) else json.dumps(raw))
    except Exception as e:
        return _tool_result(f"RED: receipt-JSON-bozuk: {e}", is_error=True)
    ns = _NODE_SECRET.encode() if _NODE_SECRET else None
    ok, msg = verify_receipt(r, node_secret=ns)
    return _tool_result(("KABUL: " if ok else "RED: ") + msg,
                        is_error=not ok)


def tool_balance(args: dict[str, Any]) -> dict[str, Any]:
    agent = str(args.get("agent", "")).strip()
    if not agent:
        return _tool_result("hata: 'agent' zorunlu", is_error=True)
    if _ENDPOINT:
        return _tool_result("remote mod: balance sester-node'unda "
                            f"({_ENDPOINT}/panel)", is_error=False)
    led = _ledger()
    spent = led.spent_today(agent)
    quota = _QUOTA
    return _tool_result(json.dumps({
        "agent": agent, "spent_today": round(spent, 6),
        "daily_quota": quota, "remaining": round(max(0.0, quota - spent), 6),
        "currency": _CURRENCY, "calls_today": led.count_today(agent),
    }, ensure_ascii=False))


def tool_history(args: dict[str, Any]) -> dict[str, Any]:
    agent = str(args.get("agent") or "").strip() or None
    limit = max(1, min(100, int(args.get("limit", 25))))
    if _ENDPOINT:
        return _tool_result("remote mod: history sester-node'unda",
                            is_error=False)
    led = _ledger()
    events = led.export_events(agent)[:limit] if agent else \
        led.export_events()[:limit]
    rows = [{"seq": e["seq"], "ts": e["ts"], "event_type": e["event_type"],
             "agent_id": e["agent_id"], "host": e["host"],
             "amount": e["amount"]} for e in events]
    return _tool_result(json.dumps({"events": rows, "count": len(rows),
                                    "chain_head": led.chain_head()},
                                   ensure_ascii=False))


TOOLS: list[dict[str, Any]] = [
    {"name": "pay",
     "description": "Bir ajan adına bir kaynağa ödeme yap ve node-cosigned "
                    "ödeme-kanıtı (receipt) al. Embedded modda lokal kanıt-"
                    "zincirine charge yazar (anahtar/testnet GEREKMEZ, $0).",
     "inputSchema": {
         "type": "object", "additionalProperties": False,
         "properties": {
             "agent": {"type": "string", "description": "ödeyen ajan kimliği"},
             "resource": {"type": "string", "description": "ödenecek kaynak "
                          "(yol; remote modda tam URL olabilir)",
                          "default": "/"},
             "amount": {"type": "number", "description": "tutar (major birim)",
                        "exclusiveMinimum": 0},
         }, "required": ["agent", "amount"]}},
    {"name": "verify_receipt",
     "description": "Bir receipt'i BAĞIMSIZ olarak doğrula — alıcı tarafı. "
                    "Sester kurulu değil, node-secret değil: proof sha256 ile "
                    "yeniden-hesaplanır. Gerçek 'ödendi' kanıtı.",
     "inputSchema": {
         "type": "object", "additionalProperties": False,
         "properties": {
             "receipt": {"type": "string", "description": "receipt JSON "
                          "(sester pay çıktısı veya herhangi bir receipt dosyası)"},
         }, "required": ["receipt"]}},
    {"name": "balance",
     "description": "Ajanın günlük harcama/kota durumunu ver (embedded mod).",
     "inputSchema": {
         "type": "object", "additionalProperties": False,
         "properties": {
             "agent": {"type": "string"},
         }, "required": ["agent"]}},
    {"name": "history",
     "description": "Kanıt-zinciri olaylarını listele (charge/red/iade).",
     "inputSchema": {
         "type": "object", "additionalProperties": False,
         "properties": {
             "agent": {"type": "string", "description": "filtre (opsiyonel)"},
             "limit": {"type": "integer", "default": 25, "minimum": 1,
                       "maximum": 100},
         }, "required": []}},
]


def _dispatch(method: str, params: Any) -> Any:
    if method == "initialize":
        return {"protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": SERVER_NAME,
                               "version": _version(),
                               "instructions": (
                                   "AI-ajan ödeme araçları. pay → öde + kanıt; "
                                   "verify_receipt → kanıtı bağımsız doğrula; "
                                   "balance/history → durum. $0/testnet mod "
                                   "varsaylandır.")}}
    if method == "notifications/initialized":
        return None  # notification — yanıt YOK
    if method == "ping":
        return {}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "tools/call":
        if not isinstance(params, dict):
            raise _RpcErr(-32602, "tools/call params nesne olmali")
        name = params.get("name")
        call_args = params.get("arguments") or {}
        for t in TOOLS:
            if t["name"] == name:
                fn = {"pay": tool_pay, "verify_receipt": tool_verify_receipt,
                      "balance": tool_balance,
                      "history": tool_history}[name]
                return fn(call_args)
        raise _RpcErr(-32602, f"bilinmeyen araç: {name}")
    if method == "tools/listChanged":  # notification (sunucu → istemci)
        return None
    raise _RpcErr(-32601, f"metod desteklenmiyor: {method}")


class _RpcErr(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code = code


def _version() -> str:
    try:
        from sester import __version__
        return __version__
    except Exception:
        return "0"


def main() -> int:
    if _ENDPOINT:
        _warn(f"remote mod: {_ENDPOINT} (embedded ledger devre-dışı)")
    buf = ""
    while True:
        chunk = sys.stdin.readline()
        if not chunk:
            break
        buf += chunk
        # JSON-RPC framed: satır-başına bir mesaj (stdio taşı standardı)
        line, _, rest = buf.partition("\n")
        if not line.strip():
            buf = rest
            continue
        buf = rest
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            _json_out(_err(-32700, "JSON ayrıştırma hatası", None))
            continue
        rid = msg.get("id")
        method = msg.get("method")
        params = msg.get("params", {})
        if not method:
            _json_out(_err(-32600, "metod yok", rid))
            continue
        try:
            result = _dispatch(method, params)
        except _RpcErr as e:
            _json_out(_err(e.code, str(e), rid))
            continue
        except Exception as e:  # araç-hatası — JSON-RPC içinde raporla
            _json_out({"jsonrpc": "2.0", "id": rid,
                       "result": _tool_result(f"araç-hatası: {e}",
                                              is_error=True)})
            continue
        if result is None:
            continue  # notification
        _json_out({"jsonrpc": "2.0", "id": rid, "result": result})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
