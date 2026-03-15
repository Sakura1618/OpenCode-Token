import sys
from pathlib import Path

from opencode_token_app.data_loader import load_usage_from_db
from opencode_token_app.exporter import export_usage_csvs
from opencode_token_app.pricing import price_loaded_usage


def parse_args(argv):
    if len(argv) < 2:
        print("用法：python export_opencode_tokens.py <opencode.db路径> [输出目录]")
        raise SystemExit(1)

    db_path = Path(argv[1]).expanduser().resolve()
    if not db_path.exists():
        print(f"数据库不存在：{db_path}")
        raise SystemExit(1)

    out_dir = Path(argv[2]).expanduser().resolve() if len(argv) >= 3 else db_path.parent / "token_export"
    return db_path, out_dir


def main():
    db_path, out_dir = parse_args(sys.argv)
    datasets = load_usage_from_db(db_path)
    datasets = price_loaded_usage(datasets, entry_path=Path(sys.argv[0]))
    export_usage_csvs(out_dir, datasets)


if __name__ == "__main__":
    main()
