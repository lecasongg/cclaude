import argparse
import json
from urllib import error, request


class ApiError(RuntimeError):
    pass


def api_call(base_url: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        f"{base_url}{path}",
        data=data,
        method=method,
        headers={"x-hermes-token": token, "content-type": "application/json"},
    )
    try:
        with request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        if exc.code == 401:
            raise ApiError("认证失败：Hermes token 和 Worker Server token 不一致。请用服务器启动时配置的 token 重新启动 Hermes。") from exc
        raise ApiError(f"HTTP {exc.code}: {exc.reason}") from exc
    except error.URLError as exc:
        raise ApiError(f"连接失败：无法连接 Worker Server（{exc.reason}）。请确认 python worker_server.py 正在运行。") from exc


def print_json(data: dict) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def run_command(base_url: str, token: str, command: str, args: list[str]) -> bool:
    if command in {"exit", "quit", "退出"}:
        return False
    if command in {"help", "帮助", "?"}:
        print("命令: workers | delegate <worker_id> <prompt> | chain <source> <target> <prompt> => <next_instruction> | exit")
        return True
    try:
        if command in {"workers", "工位", "牛马"}:
            print_json(api_call(base_url, token, "GET", "/api/workers"))
            return True
        if command in {"delegate", "派工"}:
            if len(args) < 2:
                print("用法: delegate niuma-1 分析 JSP 文件，输出需求清单")
                return True
            print_json(api_call(base_url, token, "POST", "/api/delegate", {"worker_id": args[0], "prompt": " ".join(args[1:])}))
            return True
        if command in {"chain", "链式"}:
            if len(args) < 4:
                print("用法: chain niuma-1 niuma-2 上游任务 => 下游指令")
                return True
            if "=>" in args:
                split_at = args.index("=>")
                prompt = " ".join(args[2:split_at])
                next_instruction = " ".join(args[split_at + 1:])
            else:
                prompt = args[2]
                next_instruction = " ".join(args[3:])
            print_json(
                api_call(
                    base_url,
                    token,
                    "POST",
                    "/api/chain",
                    {
                        "source_worker": args[0],
                        "target_worker": args[1],
                        "prompt": prompt,
                        "next_instruction": next_instruction,
                    },
                )
            )
            return True
    except ApiError as exc:
        print(exc)
        return True
    print("未知命令，输入 help 查看用法。")
    return True


def shell(base_url: str, token: str) -> None:
    print("Hermes 常驻主管已连接。输入 help 查看命令，exit 退出。")
    while True:
        try:
            line = input("Hermes> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        parts = line.split()
        if not run_command(base_url, token, parts[0], parts[1:]):
            return


def main() -> None:
    parser = argparse.ArgumentParser(description="Hermes PowerShell supervisor client")
    parser.add_argument("base_url")
    parser.add_argument("token")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("shell")
    subparsers.add_parser("workers")

    delegate = subparsers.add_parser("delegate")
    delegate.add_argument("worker_id")
    delegate.add_argument("prompt")

    chain = subparsers.add_parser("chain")
    chain.add_argument("source_worker")
    chain.add_argument("target_worker")
    chain.add_argument("prompt")
    chain.add_argument("next_instruction")

    args = parser.parse_args()
    try:
        if args.command in {None, "shell"}:
            shell(args.base_url, args.token)
        elif args.command == "workers":
            print_json(api_call(args.base_url, args.token, "GET", "/api/workers"))
        elif args.command == "delegate":
            print_json(
                api_call(
                    args.base_url,
                    args.token,
                    "POST",
                    "/api/delegate",
                    {"worker_id": args.worker_id, "prompt": args.prompt},
                )
            )
        else:
            print_json(
                api_call(
                    args.base_url,
                    args.token,
                    "POST",
                    "/api/chain",
                    {
                        "source_worker": args.source_worker,
                        "target_worker": args.target_worker,
                        "prompt": args.prompt,
                        "next_instruction": args.next_instruction,
                    },
                )
            )
    except ApiError as exc:
        print(exc)


if __name__ == "__main__":
    main()
