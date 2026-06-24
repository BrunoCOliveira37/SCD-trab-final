"""Valida automaticamente o resultado e o log do trabalho."""

from __future__ import annotations

import argparse
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


RESULTADO_RE = re.compile(r"^(\d+)\s*\|\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})$")
LOG_RE = re.compile(
	r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s*\|\s*(RECEBIDA|ENVIADA|SERVIDOR|CONEXAO)\s*\|\s*([A-Z]+)\s*\|\s*processo=(\d+)$"
)


@dataclass(frozen=True)
class ResultadoLinha:
	pid: int
	horario: datetime


@dataclass(frozen=True)
class LogEvento:
	horario: datetime
	direcao: str
	tipo: str
	pid: int


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Analisador automatico do trabalho")
	parser.add_argument("n", type=int)
	parser.add_argument("r", type=int)
	parser.add_argument("--resultado", default="resultado.txt")
	parser.add_argument("--log", default="coordenador.log")
	return parser.parse_args()


def ler_resultado(caminho: Path) -> list[ResultadoLinha]:
	linhas: list[ResultadoLinha] = []
	for texto in caminho.read_text(encoding="utf-8").splitlines():
		if not texto.strip():
			continue
		correspondencia = RESULTADO_RE.match(texto.strip())
		if not correspondencia:
			raise ValueError(f"linha invalida em resultado.txt: {texto!r}")
		pid = int(correspondencia.group(1))
		horario = datetime.strptime(correspondencia.group(2), "%Y-%m-%d %H:%M:%S.%f")
		linhas.append(ResultadoLinha(pid=pid, horario=horario))
	return linhas


def ler_log(caminho: Path) -> list[LogEvento]:
	eventos: list[LogEvento] = []
	for texto in caminho.read_text(encoding="utf-8").splitlines():
		correspondencia = LOG_RE.match(texto.strip())
		if not correspondencia:
			continue
		horario = datetime.strptime(correspondencia.group(1), "%Y-%m-%d %H:%M:%S.%f")
		direcao = correspondencia.group(2)
		tipo = correspondencia.group(3)
		pid = int(correspondencia.group(4))
		eventos.append(LogEvento(horario=horario, direcao=direcao, tipo=tipo, pid=pid))
	return eventos


def validar_resultado(linhas: list[ResultadoLinha], n: int, r: int) -> list[str]:
	erros: list[str] = []
	esperado = n * r
	if len(linhas) != esperado:
		erros.append(f"resultado.txt deveria ter {esperado} linhas, mas tem {len(linhas)}")

	contagem = Counter(linha.pid for linha in linhas)
	for pid in range(1, n + 1):
		if contagem[pid] != r:
			erros.append(f"processo {pid} aparece {contagem[pid]} vezes em vez de {r}")

	horarios = [linha.horario for linha in linhas]
	if horarios != sorted(horarios):
		erros.append("os horarios de resultado.txt nao estao em ordem crescente")

	return erros


def validar_log(eventos: list[LogEvento]) -> list[str]:
	erros: list[str] = []
	requests: list[int] = []
	grants: list[int] = []
	releases: list[int] = []
	owner: int | None = None

	# Percorre todos os eventos na ordem do log e coleta os eventos relevantes
	for evento in eventos:
		if evento.direcao == "RECEBIDA" and evento.tipo == "REQUEST":
			requests.append(evento.pid)

		elif evento.direcao == "ENVIADA" and evento.tipo == "GRANT":
			if owner is not None:
				erros.append(f"dois GRANT sem RELEASE intermediario: proprietario atual {owner}, novo {evento.pid}")
			owner = evento.pid
			grants.append(evento.pid)

		elif evento.direcao == "RECEBIDA" and evento.tipo == "RELEASE":
			# RELEASE deve corresponder ao owner atual
			if owner != evento.pid:
				erros.append(f"RELEASE de {evento.pid} nao corresponde ao proprietario atual {owner}")
			releases.append(evento.pid)
			owner = None

	if owner is not None:
		erros.append(f"o log terminou com o processo {owner} ainda na regiao critica")

	# Verificacoes de ordem e correspondencia
	if requests != grants:
		erros.append("a ordem FIFO dos pedidos/grants nao foi respeitada")

	if grants != releases:
		erros.append("nem todo GRANT teve um RELEASE correspondente na mesma ordem")

	# Verificacao de exclusao mutua: nunca mais de um dentro da regiao critica ao mesmo tempo
	estados = 0
	for evento in eventos:
		if evento.direcao == "ENVIADA" and evento.tipo == "GRANT":
			estados += 1
			if estados > 1:
				erros.append("mais de um processo simultaneamente na regiao critica")
				break
		elif evento.direcao == "RECEBIDA" and evento.tipo == "RELEASE":
			estados -= 1
			if estados < 0:
				erros.append("RELEASE recebido antes de qualquer GRANT")
				break

	return erros


def imprimir_relatorio(erros: list[str]) -> int:
	if erros:
		print("Violacoes encontradas:")
		for erro in erros:
			print(f"- {erro}")
		return 1

	print("Validacao concluida sem violacoes")
	return 0


def main() -> int:
	args = parse_args()
	resultado = Path(args.resultado)
	log = Path(args.log)

	erros = validar_resultado(ler_resultado(resultado), args.n, args.r)
	erros.extend(validar_log(ler_log(log)))
	return imprimir_relatorio(erros)


if __name__ == "__main__":
	raise SystemExit(main())
