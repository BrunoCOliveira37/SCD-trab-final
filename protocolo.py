"""Funcoes de protocolo para o trabalho de exclusao mutua."""

from __future__ import annotations

from typing import Tuple

F = 32

REQUEST = 1
GRANT = 2
RELEASE = 3

NOMES_TIPO = {
	REQUEST: "REQUEST",
	GRANT: "GRANT",
	RELEASE: "RELEASE",
}


def criar_mensagem(tipo: int, pid: int) -> bytes:
	"""Cria uma mensagem fixa de exatamente F bytes."""

	if tipo not in NOMES_TIPO:
		raise ValueError(f"tipo invalido: {tipo}")
	if pid < 0:
		raise ValueError(f"pid invalido: {pid}")

	corpo = f"{tipo}|{pid}|".encode("ascii")
	if len(corpo) > F:
		raise ValueError("mensagem maior que o tamanho fixo")
	return corpo.ljust(F, b"0")


def interpretar_mensagem(mensagem: bytes) -> Tuple[int, int]:
	"""Interpreta uma mensagem fixa recebida do socket."""

	texto = mensagem.decode("ascii", errors="ignore").rstrip("0").strip()
	partes = texto.split("|")
	if len(partes) < 2:
		raise ValueError(f"mensagem invalida: {texto!r}")

	tipo = int(partes[0])
	pid = int(partes[1])
	if tipo not in NOMES_TIPO:
		raise ValueError(f"tipo invalido: {tipo}")
	if pid < 0:
		raise ValueError(f"pid invalido: {pid}")
	return tipo, pid


def receber_exatamente(sock, quantidade: int) -> bytes:
	"""Lê exatamente a quantidade solicitada ou retorna bytes vazios ao fechar."""

	dados = bytearray()
	while len(dados) < quantidade:
		bloco = sock.recv(quantidade - len(dados))
		if not bloco:
			break
		dados.extend(bloco)
	return bytes(dados)


def nome_tipo(tipo: int) -> str:
	return NOMES_TIPO.get(tipo, f"TIPO_{tipo}")

