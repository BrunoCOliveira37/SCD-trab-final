"""Coordenador centralizado de exclusao mutua distribuida."""

from __future__ import annotations

import argparse
import queue
import socket
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Deque, Dict, Optional, Tuple

from protocolo import F, GRANT, REQUEST, RELEASE, criar_mensagem, interpretar_mensagem, nome_tipo, receber_exatamente


@dataclass(frozen=True)
class Evento:
	tipo: int
	pid: int
	conexao: socket.socket


class Coordenador:
	def __init__(self, host: str, port: int, log_path: str = "coordenador.log") -> None:
		self.host = host
		self.port = port
		self.log_path = log_path
		self.stop_event = threading.Event()
		self.eventos: "queue.Queue[Evento]" = queue.Queue()
		self.lock = threading.Lock()
		self.fila_pedidos: Deque[int] = deque()
		self.processo_na_regiao_critica: Optional[int] = None
		self.sockets_por_pid: Dict[int, socket.socket] = {}
		self.pid_por_socket: Dict[socket.socket, int] = {}
		self.quantidade_atendimentos: Dict[int, int] = {}
		self.servidor: Optional[socket.socket] = None
		self.threads: list[threading.Thread] = []
		# abrir em modo "w" para reiniciar o log a cada execucao
		self.arquivo_log = open(self.log_path, "w", encoding="utf-8", buffering=1)

	def iniciar(self) -> None:
		self._abrir_servidor()
		self._iniciar_threads()
		try:
			while not self.stop_event.wait(0.25):
				pass
		except KeyboardInterrupt:
			self.encerrar()
		finally:
			self.encerrar()

	def _abrir_servidor(self) -> None:
		servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		servidor.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		servidor.bind((self.host, self.port))
		servidor.listen()
		servidor.settimeout(1.0)
		self.servidor = servidor
		self._log_texto(f"{self._agora()} | SERVIDOR | INICIADO | porta={self.port}")

	def _iniciar_threads(self) -> None:
		self._adicionar_thread(self._thread_aceitar_conexoes, "aceitacao")
		self._adicionar_thread(self._thread_processar_eventos, "algoritmo")
		self._adicionar_thread(self._thread_comandos_terminal, "terminal")

	def _adicionar_thread(self, alvo, nome: str) -> None:
		thread = threading.Thread(target=alvo, name=f"coordenador-{nome}", daemon=True)
		thread.start()
		self.threads.append(thread)

	def _agora(self) -> str:
		return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

	def _log(self, direcao: str, tipo: int, pid: int) -> None:
		self._log_texto(f"{self._agora()} | {direcao:<8} | {nome_tipo(tipo):<7} | processo={pid}")

	def _log_texto(self, texto: str) -> None:
		self.arquivo_log.write(texto + "\n")

	def _thread_aceitar_conexoes(self) -> None:
		assert self.servidor is not None
		while not self.stop_event.is_set():
			try:
				conexao, endereco = self.servidor.accept()
			except socket.timeout:
				continue
			except OSError:
				break

			conexao.settimeout(None)
			self._log_texto(f"{self._agora()} | CONEXAO | ACEITA  | origem={endereco[0]}:{endereco[1]}")
			thread = threading.Thread(
				target=self._thread_receber_mensagens,
				args=(conexao,),
				name=f"recebedor-{endereco[1]}",
				daemon=True,
			)
			thread.start()
			self.threads.append(thread)

	def _thread_receber_mensagens(self, conexao: socket.socket) -> None:
		pid_conhecido: Optional[int] = None
		try:
			while not self.stop_event.is_set():
				dados = receber_exatamente(conexao, F)
				if len(dados) < F:
					break
				tipo, pid = interpretar_mensagem(dados)
				pid_conhecido = pid
				with self.lock:
					self.sockets_por_pid[pid] = conexao
					self.pid_por_socket[conexao] = pid
				self._log("RECEBIDA", tipo, pid)
				self.eventos.put(Evento(tipo=tipo, pid=pid, conexao=conexao))
		except OSError:
			pass
		except ValueError:
			pass
		finally:
			if pid_conhecido is not None:
				self.eventos.put(Evento(tipo=0, pid=pid_conhecido, conexao=conexao))
			self._remover_conexao(conexao)

	def _remover_conexao(self, conexao: socket.socket) -> None:
		with self.lock:
			pid = self.pid_por_socket.pop(conexao, None)
			if pid is not None:
				self.sockets_por_pid.pop(pid, None)
				try:
					self.fila_pedidos.remove(pid)
				except ValueError:
					pass
				if self.processo_na_regiao_critica == pid:
					self.processo_na_regiao_critica = None
		try:
			conexao.close()
		except OSError:
			pass

	def _thread_processar_eventos(self) -> None:
		while not self.stop_event.is_set():
			try:
				evento = self.eventos.get(timeout=0.5)
			except queue.Empty:
				continue

			if evento.tipo == REQUEST:
				self._processar_request(evento.pid, evento.conexao)
			elif evento.tipo == RELEASE:
				self._processar_release(evento.pid)
			else:
				self._processar_desconexao(evento.pid)

	def _processar_request(self, pid: int, conexao: socket.socket) -> None:
		with self.lock:
			if pid not in self.sockets_por_pid:
				self.sockets_por_pid[pid] = conexao
			if pid not in self.fila_pedidos and self.processo_na_regiao_critica != pid:
				self.fila_pedidos.append(pid)
		self._tentar_atender()

	def _processar_release(self, pid: int) -> None:
		with self.lock:
			if self.processo_na_regiao_critica != pid:
				return
			self.processo_na_regiao_critica = None
		self._tentar_atender()

	def _processar_desconexao(self, pid: int) -> None:
		with self.lock:
			self.sockets_por_pid.pop(pid, None)
			try:
				self.fila_pedidos.remove(pid)
			except ValueError:
				pass
			if self.processo_na_regiao_critica == pid:
				self.processo_na_regiao_critica = None
		self._tentar_atender()

	def _tentar_atender(self) -> None:
		while not self.stop_event.is_set():
			with self.lock:
				if self.processo_na_regiao_critica is not None:
					return
				pid = self._proximo_pid_esperando()
				if pid is None:
					return
				conexao = self.sockets_por_pid.get(pid)
				if conexao is None:
					continue
				self.processo_na_regiao_critica = pid
				self.quantidade_atendimentos[pid] = self.quantidade_atendimentos.get(pid, 0) + 1

			if self._enviar(pid, GRANT):
				return

			with self.lock:
				if self.processo_na_regiao_critica == pid:
					self.processo_na_regiao_critica = None

	def _proximo_pid_esperando(self) -> Optional[int]:
		while self.fila_pedidos:
			pid = self.fila_pedidos.popleft()
			if pid in self.sockets_por_pid:
				return pid
		return None

	def _enviar(self, pid: int, tipo: int) -> bool:
		with self.lock:
			conexao = self.sockets_por_pid.get(pid)
		if conexao is None:
			return False
		try:
			conexao.sendall(criar_mensagem(tipo, pid))
			self._log("ENVIADA", tipo, pid)
			return True
		except OSError:
			self._processar_desconexao(pid)
			return False

	def _thread_comandos_terminal(self) -> None:
		while not self.stop_event.is_set():
			try:
				comando = input().strip()
			except EOFError:
				self.stop_event.set()
				break
			except KeyboardInterrupt:
				self.stop_event.set()
				break

			if comando == "1":
				self._imprimir_fila()
			elif comando == "2":
				self._imprimir_atendimentos()
			elif comando == "3":
				self.stop_event.set()
				break

	def _snapshot_fila(self) -> list[int]:
		with self.lock:
			return list(self.fila_pedidos)

	def _snapshot_atendimentos(self) -> Dict[int, int]:
		with self.lock:
			return dict(self.quantidade_atendimentos)

	def _imprimir_fila(self) -> None:
		fila = self._snapshot_fila()
		if fila:
			print("Fila atual:", fila)
		else:
			print("Fila atual: vazia")

	def _imprimir_atendimentos(self) -> None:
		atendimentos = self._snapshot_atendimentos()
		if not atendimentos:
			print("Nenhum processo atendido ainda")
			return
		print("Atendimentos por processo:")
		for pid in sorted(atendimentos):
			print(f"processo {pid}: {atendimentos[pid]}")

	def encerrar(self) -> None:
		if self.stop_event.is_set() and self.servidor is None:
			return
		self.stop_event.set()
		servidor = self.servidor
		self.servidor = None
		if servidor is not None:
			try:
				servidor.close()
			except OSError:
				pass
		with self.lock:
			conexoes = list(self.sockets_por_pid.values())
			self.sockets_por_pid.clear()
			self.pid_por_socket.clear()
			self.fila_pedidos.clear()
			self.processo_na_regiao_critica = None
		for conexao in conexoes:
			try:
				conexao.close()
			except OSError:
				pass
		try:
			self.arquivo_log.close()
		except OSError:
			pass


def parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="Coordenador centralizado de exclusao mutua")
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=5000)
	parser.add_argument("--log", default="coordenador.log")
	return parser.parse_args()


def main() -> int:
	args = parse_args()
	coordenador = Coordenador(args.host, args.port, args.log)
	coordenador.iniciar()
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
