"""Inicializa varios processos clientes sem atraso proposital."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Inicializador dos processos")
	parser.add_argument("n", type=int)
	parser.add_argument("r", type=int)
	parser.add_argument("k", type=float)
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=5000)
	parser.add_argument("--resultado", default="resultado.txt")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	pasta = Path(__file__).resolve().parent
	arquivo_resultado = pasta / args.resultado
	arquivo_resultado.write_text("", encoding="utf-8")

	processos: list[subprocess.Popen[bytes]] = []
	for pid in range(1, args.n + 1):
		comando = [
			sys.executable,
			str(pasta / "processo.py"),
			str(pid),
			args.host,
			str(args.port),
			str(args.r),
			str(args.k),
			"--resultado",
			str(arquivo_resultado),
		]
		processos.append(subprocess.Popen(comando))

	codigo = 0
	for processo in processos:
		retorno = processo.wait()
		if retorno != 0 and codigo == 0:
			codigo = retorno
	return codigo


if __name__ == "__main__":
	raise SystemExit(main())
