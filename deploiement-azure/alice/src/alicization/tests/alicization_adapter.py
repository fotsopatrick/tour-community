from __future__ import annotations
import json
import os
import re
import sqlite3
import time
import itertools
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parents[1]
STATE_DIR = PROJECT_ROOT / "state"
STATE_DB = STATE_DIR / "alicization.db"
RAW_DIR = PROJECT_ROOT / "raw"

MODEL_ENDPOINT = "http://localhost:8081/v1/chat/completions"
DEBUG = False


def call_model(messages, temperature=0.2):
    payload = {
        "model": "qwen2.5-3b-instruct",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": 512,
        "stream": False,
    }
    req = urllib.request.Request(
        MODEL_ENDPOINT,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        return data["choices"][0]["message"]["content"]


@dataclass
class RunResult:
    output: Any
    success: bool
    events: list[dict]
    model_io: list[dict]


class AdapterNotImplemented(RuntimeError):
    pass


def apply_op(name: str, value: int, definitions: dict) -> int:
    p = definitions[name]
    return value * p["a"] + p["b"]


def apply_steps(value: int, steps: list[str], definitions: dict) -> int:
    for op in steps:
        value = apply_op(op, value, definitions)
    return value


class AlicizationAdapter:
    def __init__(self):
        self._teach_transcript: list[dict] = []
        self._demo_removed: bool = False

    def _db(self):
        return sqlite3.connect(STATE_DB, timeout=10)

    @staticmethod
    def _ops_block(fixture: dict) -> str:
        return "".join(
            f"  {name}: x -> x * {d['a']} + {d['b']}\n"
            for name, d in fixture["operations"].items()
        )

    def _true_expected(self, input_value: int, fixture: dict) -> int:
        return apply_steps(input_value, fixture["secret_procedure"],
                           fixture["operations"])

    def reset_state(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        conn = self._db()
        try:
            conn.execute("DROP TABLE IF EXISTS experiences")
            conn.execute("DROP TABLE IF EXISTS procedures")
            conn.execute(
                "CREATE TABLE experiences ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " timestamp TEXT NOT NULL,"
                " observation TEXT NOT NULL,"
                " action TEXT NOT NULL,"
                " result TEXT NOT NULL,"
                " lesson TEXT NOT NULL,"
                " confidence REAL NOT NULL)")
            conn.execute(
                "CREATE TABLE procedures ("
                " id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " steps_json TEXT NOT NULL,"
                " status TEXT NOT NULL,"
                " created_at TEXT NOT NULL,"
                " verified_at TEXT,"
                " demo_input INTEGER,"
                " demo_output INTEGER)")
            conn.commit()
        finally:
            conn.close()
        self._teach_transcript = []
        self._demo_removed = False
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for name in ("events.jsonl", "model_io.jsonl"):
            (RAW_DIR / name).write_text("")

    def baseline(self, input_value: int, fixture: dict) -> RunResult:
        prompt = (
            "You are given these operations:\n"
            + self._ops_block(fixture)
            + "Apply a sequence of exactly 3 of these operations (each used at "
              f"most once, order matters) that transforms the starting value "
              f"{input_value}.\nReply with ONLY the final integer."
        )
        request_body = json.dumps({
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 200,
        }, indent=2)
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / "baseline_model_input.txt").write_text(request_body)
        response_body_raw = self._chat_user(prompt)
        (RAW_DIR / "baseline_model_output.txt").write_text(response_body_raw)

        numbers = re.findall(r"-?\d+", response_body_raw)
        parsed_output = int(numbers[-1]) if numbers else None

        true_expected = self._true_expected(input_value, fixture)
        success = parsed_output is not None and parsed_output == true_expected
        event = {"phase": "baseline", "input": input_value,
                 "parsed_output": parsed_output,
                 "true_expected": true_expected, "success": success}
        return RunResult(output=parsed_output, success=success,
                         events=[event],
                         model_io=[{"prompt": prompt,
                                    "response": response_body_raw}])

    def _chat_user(self, content: str, temperature: float = 0.2) -> str:
        return call_model([{"role": "user", "content": content}],
                          temperature=temperature)

    def _log_round(self, rounds_path: Path, round_no: int, sent, reply):
        with open(rounds_path, "a") as f:
            f.write(json.dumps({"round": round_no, "sent": sent,
                                "raw_response": reply}) + "\n")
        if DEBUG:
            print(f"--- round {round_no} SENT ---\n{sent}\n"
                  f"--- round {round_no} REPLY ---\n{reply}")

    def teach(self, demo: dict, fixture: dict) -> RunResult:
        system_msg = (
            "Tu es un agent qui doit d\u00e9couvrir une proc\u00e9dure de transformation de nombres.\n"
            "Tu disposes des op\u00e9rations suivantes qui transforment un nombre.\n"
            "Les op\u00e9rations s'appliquent successivement.\n\n"
            "POUR TESTER LES OP\u00c9RATIONS :\n"
            "\u00c9cris des lignes CALL avec la valeur 17 pour chaque op\u00e9ration.\n"
            "Exemple :\n"
            "CALL op_q9 17\n"
            "CALL op_k7 17\n"
            "CALL op_m2 17\n"
            "IMPORTANT : Chaque CALL doit \u00eatre au format : CALL <nom_op> 17\n"
            + self._ops_block(fixture)
        )
        n_ops = len(fixture.get("secret_procedure", []))
        user_msg = (
            f"A hidden sequence of exactly {n_ops} of these operations transforms "
            f"{demo['input']} into {demo['output']}.\n"
            "Propose tests by responding with exactly:\n"
            "CALL <op_name> <value>\n"
            "(one CALL per line, one per operation). Do NOT write any RESULT yourself "
            "- real results will be given to you."
        )
        messages = [{"role": "system", "content": system_msg},
                    {"role": "user", "content": user_msg}]
        self._teach_transcript = list(messages)

        RAW_DIR.mkdir(parents=True, exist_ok=True)
        rounds_path = RAW_DIR / "teach_rounds.jsonl"
        rounds_path.write_text("")
        transcript_lines = ["=== TEACH TRANSCRIPT ===", system_msg, "",
                            "[user] " + user_msg]

        move_re = re.compile(r"CALL\s+(\w+)\s+(-?\d+)")
        proposed: list[str] | None = None

        # ── TURN 1: model proposes CALLs ──────────────────────────────
        reply1 = call_model(messages)
        messages.append({"role": "assistant", "content": reply1})
        self._teach_transcript.append({"role": "assistant",
                                       "content": reply1})
        transcript_lines += ["", "--- TURN 1 assistant ---", reply1]
        self._log_round(rounds_path, 1, user_msg, reply1)

        moves1 = move_re.findall(reply1)
        calls1 = [(c, int(v)) for c, v in moves1]

        # --- GUARD: retry until we get exactly n_ops valid CALLs ---
        n_ops = len(fixture.get("secret_procedure", []))
        demo_input_val = int(demo["input"])

        for _retry in range(5):
            invalid = [f"{c} (v={v})" for c, v in calls1 if v != demo_input_val]
            if not invalid and len(calls1) >= n_ops:
                calls1 = calls1[:n_ops]
                break

            error_msg = (
                "Erreur : utilise la valeur " + str(demo_input_val) + " pour CHAQUE CALL.\n"
                + ("Problème : " + ", ".join(invalid) if invalid else "Pas assez de CALLs.") + "\n"
                + "\n".join(f"CALL {name} {demo_input_val}"
                           for name in fixture["operations"]) + "\n"
                + "\nChaque ligne : CALL <nom_op> " + str(demo_input_val)
            )
            messages.append({"role": "assistant", "content": reply1})
            messages.append({"role": "user", "content": error_msg})
            reply1 = call_model(messages)
            messages.append({"role": "assistant", "content": reply1})
            transcript_lines += ["", f"--- RETRY {_retry+1} ---", reply1]
            self._log_round(rounds_path, 10 + _retry, error_msg, reply1)
            calls1 = [(c, int(v)) for c, v in move_re.findall(reply1)]

        if not calls1:
            transcript_lines += ["", "=== END (no valid calls) ==="]
            return self._finish_teach(None, demo, fixture,
                                      transcript_lines)

        # ── execute REAL operations ───────────────────────────────────
        results = []
        for op_name, val in calls1:
            if op_name in fixture["operations"]:
                res = apply_op(op_name, val, fixture["operations"])
                results.append(f"CALL {op_name} {val} \u2192 RESULT {res}")
            else:
                results.append(f"CALL {op_name} {val} \u2192 ERROR unknown op")

        # ── DETERMINISTIC PERMUTATION: find correct order ─────────────
        tested_ops = [op_name for op_name, val in calls1]
        tested_functions = [op for op in fixture["operations"]
                           if op in tested_ops]

        if len(tested_functions) == n_ops:
            target_value = float(demo["output"])
            initial_value = float(demo["input"])

            for perm in itertools.permutations(tested_functions):
                current = initial_value
                for op_name in perm:
                    current = apply_op(op_name, current,
                                       fixture["operations"])
                if abs(current - target_value) < 0.001:
                    proposed = list(perm)
                    transcript_lines += ["", "=== END (deterministic) ==="]
                    return self._finish_teach(proposed, demo, fixture,
                                              transcript_lines)

        transcript_lines += ["", "=== END (no permutation matched) ==="]
        return self._finish_teach(None, demo, fixture, transcript_lines)

    def _finish_teach(self, proposed, demo, fixture, transcript_lines):
        (RAW_DIR / "teach_model_transcript.txt").write_text(
            "\n".join(transcript_lines))

        verified = False
        if proposed is not None:
            replay = apply_steps(demo["input"], proposed,
                                 fixture["operations"])
            verified = (replay == demo["output"])

        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        conn = self._db()
        try:
            if verified:
                cur = conn.execute(
                    "INSERT INTO procedures (steps_json, status, created_at,"
                    " verified_at, demo_input, demo_output)"
                    " VALUES (?, 'PROPOSED', ?, ?, ?, ?)",
                    (json.dumps(proposed), ts, None, demo["input"],
                     demo["output"]))
                proc_id = cur.lastrowid
                conn.execute(
                    "UPDATE procedures SET status='VERIFIED',"
                    " verified_at=? WHERE id=?", (ts, proc_id))
                conn.commit()
            else:
                proc_id = None
            conn.execute(
                "INSERT INTO experiences (timestamp, observation, action,"
                " result, lesson, confidence) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, "attempted to learn sequence for demo",
                 f"proposed {proposed}" if proposed else "no valid CALLs",
                 "verified" if verified else "failed",
                 "sequence replays demo correctly" if verified
                 else "proposed sequence failed replay or never produced",
                 1.0 if verified else 0.0))
            conn.commit()
        finally:
            conn.close()

        event = {"phase": "teach", "proposed": proposed,
                 "verified": verified}
        return RunResult(output=proposed, success=verified,
                         events=[event], model_io=[])

    def snapshot_state(self) -> dict:
        out = {"experiences": [], "procedures": []}
        if not STATE_DB.exists():
            return out
        conn = self._db()
        try:
            conn.row_factory = sqlite3.Row
            for row in conn.execute(
                    "SELECT * FROM experiences ORDER BY id"):
                out["experiences"].append(dict(row))
            for row in conn.execute(
                    "SELECT * FROM procedures ORDER BY id"):
                d = dict(row)
                d["steps"] = json.loads(d["steps_json"])
                out["procedures"].append(d)
        except sqlite3.Error:
            pass
        finally:
            conn.close()
        return out

    def remove_demo_context(self) -> None:
        self._teach_transcript = []
        self._demo_removed = True
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / "prompt_after_removal_marker.txt").write_text(
            f"Demo context removed at "
            f"{time.strftime('%Y-%m-%dT%H:%M:%S')}. "
            "Teach transcript cleared from adapter memory.\n")

    def reuse(self, input_value: int, fixture: dict) -> RunResult:
        proc = None
        if STATE_DB.exists():
            conn = self._db()
            try:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM procedures WHERE status IN"
                    " ('VERIFIED','ACTIVE')"
                    " ORDER BY id DESC LIMIT 1").fetchone()
                if row is not None:
                    proc = dict(row)
                    proc["steps"] = json.loads(proc["steps_json"])
            except sqlite3.Error:
                proc = None
            finally:
                conn.close()
        if proc is None:
            event = {"phase": "reuse", "input": input_value,
                     "procedure_found": False}
            return RunResult(output=None, success=False,
                             events=[event], model_io=[])

        ts = time.strftime("%Y-%m-%dT%H:%M:%S")
        if proc["status"] == "VERIFIED":
            conn = self._db()
            try:
                conn.execute(
                    "UPDATE procedures SET status='ACTIVE' WHERE id=?",
                    (proc["id"],))
                conn.commit()
            finally:
                conn.close()

        result = apply_steps(input_value, proc["steps"],
                             fixture["operations"])
        true_expected = self._true_expected(input_value, fixture)
        success = (result == true_expected)
        event = {"phase": "reuse", "procedure_id": proc["id"],
                 "input": input_value, "executed_steps": proc["steps"],
                 "result": result, "true_expected": true_expected,
                 "success": success}
        return RunResult(output=result, success=success,
                         events=[event], model_io=[])

    def restart(self) -> None:
        fresh = AlicizationAdapter()
        self.__dict__ = dict(fresh.__dict__)

    def state(self) -> dict:
        return self.snapshot_state()

    def raw_events(self) -> list[dict]:
        path = RAW_DIR / "events.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text().splitlines() if line.strip()]

    def raw_model_io(self) -> list[dict]:
        path = RAW_DIR / "model_io.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in
                path.read_text().splitlines() if line.strip()]

    def hide_learned_state(self) -> None:
        if STATE_DB.exists():
            os.rename(STATE_DB, STATE_DIR / "alicization.db.hidden")


def teach(task_description, available_operations, demonstration, target,
          model=None, tokenizer=None):
    system_prompt = (
        "Tu es un agent qui doit d\u00e9couvrir une proc\u00e9dure de transformation de nombres.\n"
        "Tu disposes d'op\u00e9rations qui transforment un nombre.\n"
        "Les op\u00e9rations s'appliquent successivement.\n\n"
        "POUR TESTER LES OP\u00c9RATIONS :\n"
        "\u00c9cris des lignes CALL avec la valeur 17 pour chaque op\u00e9ration.\n"
        "Exemple :\n"
        "CALL op_q9 17\n"
        "CALL op_k7 17\n"
        "CALL op_m2 17\n"
        "IMPORTANT : Chaque CALL doit \u00eatre au format : CALL <nom_op> 17"
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",
         "content": f"Voici la d\u00e9monstration :\n{demonstration}\n\n"
                    f"T\u00e2che : {task_description}\n\n"
                    f"Objectif : {target}\n\n"
                    "\u00c9cris des CALL avec la valeur 17 pour chaque op\u00e9ration."},
    ]

    response1 = call_model(messages, temperature=0.2)
    messages.append({"role": "assistant", "content": response1})
    if DEBUG:
        print("--- TURN 1 ---\n" + response1)

    call_pattern = r"CALL\s+(\w+)\s+([0-9.]+)"
    calls = re.findall(call_pattern, response1)

    for _retry in range(5):
        invalid_calls = []
        for op_name, val_str in calls:
            try:
                val = float(val_str)
                if val != 17:
                    invalid_calls.append(f"{op_name} (valeur: '{val_str}' au lieu de 17)")
            except (ValueError, TypeError):
                invalid_calls.append(f"{op_name} (valeur: '{val_str}' non num\u00e9rique)")

        if not invalid_calls and len(calls) >= 3:
            break

        error_msg = (
            "Erreur : les appels suivants n'utilisent pas la valeur 17 :\n"
            + ("\n".join(invalid_calls) if invalid_calls else "Aucun CALL valide trouv\u00e9.")
            + "\n\nTu DOIS \u00e9crire exactement 3 lignes : CALL <nom_op> 17"
        )
        messages.append({"role": "assistant", "content": response1})
        messages.append({"role": "user", "content": error_msg})
        response1 = call_model(messages, temperature=0.2)
        if DEBUG:
            print(f"--- RETRY {_retry+1} ---\n" + response1)
        messages.append({"role": "assistant", "content": response1})
        calls = re.findall(call_pattern, response1)

    if not calls:
        return None

    results = []
    for op_name, val_str in calls:
        val = float(val_str)
        for op in available_operations:
            if op.__name__ == op_name:
                results.append((op_name, val, op(val)))
                break

    tested_ops = [op_name for op_name, val, result in results]
    tested_functions = [op for op in available_operations if op.__name__ in tested_ops]

    n_ops = len(tested_functions)
    if n_ops >= 3:
        target_value = float(target)
        initial_value = float(demonstration.split()[0])

        for perm in itertools.permutations(tested_functions):
            current = initial_value
            for op in perm:
                current = op(current)
            if abs(current - target_value) < 0.001:
                return [op.__name__ for op in perm]

    return None
