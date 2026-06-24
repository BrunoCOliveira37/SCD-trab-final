"""Cliente que solicita acesso ao coordenador e escreve em resultado.txt."""

from __future__ import annotations

import argparse
import socket
import sys
import time
from datetime import datetime
from pathlib import Path

from protocolo import F, GRANT, RELEASE, REQUEST, criar_mensagem, interpretar_mensagem, receber_exatamente


def agora_formatado() -> str:
	return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def conectar(host: str, port: int, tentativas: int = 40, pausa: float = 0.25) -> socket.socket:
	ultimo_erro: Exception | None = None
	for _ in range(tentativas):
		try:
			conexao = socket.create_connection((host, port), timeout=3.0)
			conexao.settimeout(None)
			return conexao
		except OSError as erro:
			ultimo_erro = erro
			time.sleep(pausa)
	raise ConnectionError(f"nao foi possivel conectar ao coordenador: {ultimo_erro}")


def enviar(conexao: socket.socket, tipo: int, pid: int) -> None:
	conexao.sendall(criar_mensagem(tipo, pid))


def aguardar_tipo(conexao: socket.socket, tipo_esperado: int, pid: int) -> None:
	dados = receber_exatamente(conexao, F)
	if len(dados) < F:
		raise ConnectionError("coordenador encerrou a conexao")
	tipo, pid_recebido = interpretar_mensagem(dados)
	if tipo != tipo_esperado or pid_recebido != pid:
		raise ValueError(f"mensagem inesperada: tipo={tipo} pid={pid_recebido}")


def escrever_resultado(arquivo: Path, pid: int) -> None:
	linha = f"{pid} | {agora_formatado()}\n"
	with arquivo.open("a", encoding="utf-8") as saida:
		saida.write(linha)


def executar(pid: int, host: str, port: int, repeticoes: int, descanso: float, arquivo_resultado: Path) -> int:
	conexao = conectar(host, port)
	try:
		for _ in range(repeticoes):
			enviar(conexao, REQUEST, pid)
			aguardar_tipo(conexao, GRANT, pid)
			escrever_resultado(arquivo_resultado, pid)
			time.sleep(descanso)
			enviar(conexao, RELEASE, pid)
	finally:
		try:
			conexao.close()
		except OSError:
			pass
	return 0


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Processo cliente para exclusao mutua")
	parser.add_argument("pid", type=int)
	parser.add_argument("host")
	parser.add_argument("port", type=int)
	parser.add_argument("r", type=int)
	parser.add_argument("k", type=float)
	parser.add_argument("--resultado", default="resultado.txt")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	arquivo_resultado = Path(args.resultado)
	return executar(args.pid, args.host, args.port, args.r, args.k, arquivo_resultado)


if __name__ == "__main__":
	raise SystemExit(main())
