# Trabalho de Exclusão Mútua em Sistemas Distribuídos

## 1. Objetivo

Implementar o algoritmo centralizado de exclusão mútua distribuída. Vários processos devem solicitar ao coordenador permissão para acessar uma região crítica e escrever no mesmo arquivo `resultado.txt`.

Além do programa, o trabalho exige:

- testes em diferentes cenários;
- relatório de no máximo 6 páginas;
- apresentação de no máximo 6 minutos;
- trabalho realizado em trio.

## 2. Arquitetura sugerida

```text
launcher
   ├── processo 1 ─┐
   ├── processo 2 ─┼── sockets TCP ── coordenador
   └── processo n ─┘                      │
                                         ├── fila de pedidos
                                         ├── log
                                         └── interface no terminal

Todos os processos escrevem no mesmo resultado.txt.
```

Recomenda-se usar sockets TCP, pois eles oferecem entrega confiável e mantêm a ordem dos dados.

## 3. Estrutura de arquivos

```text
trab_final/
├── coordenador.py
├── processo.py
├── launcher.py
├── protocolo.py
├── analisar.py
├── resultado.txt
├── coordenador.log
└── README.md
```

- `protocolo.py`: cria, interpreta e recebe mensagens.
- `coordenador.py`: servidor e algoritmo de exclusão mútua.
- `processo.py`: cliente que solicita acesso à região crítica.
- `launcher.py`: inicia os `n` processos sem intervalo proposital.
- `analisar.py`: valida automaticamente o resultado e o log.

## 4. Protocolo de mensagens

O programa deve ter exatamente os três tipos de mensagem definidos no enunciado:

| Código | Mensagem | Função |
|---|---|---|
| `1` | `REQUEST` | Solicitar acesso à região crítica |
| `2` | `GRANT` | Autorizar o acesso |
| `3` | `RELEASE` | Informar a liberação da região crítica |

Defina um tamanho fixo para todas as mensagens, por exemplo:

```python
F = 32
```

Formato sugerido:

```text
TIPO|PID|PREENCHIMENTO
```

Exemplo:

```text
1|3|0000000000000000000000000000
```

Funções necessárias em `protocolo.py`:

```python
criar_mensagem(tipo, pid) -> bytes
interpretar_mensagem(mensagem) -> tuple
receber_exatamente(socket, quantidade) -> bytes
```

> Um único `socket.recv(F)` não garante o recebimento dos `F` bytes. A função `receber_exatamente` deve repetir a leitura até receber tudo ou detectar que a conexão foi encerrada.

## 5. Coordenador

O coordenador deve manter:

```python
fila_pedidos
processo_na_regiao_critica
sockets_por_pid
quantidade_atendimentos
```

Use uma fila FIFO para atender os processos na ordem em que fizeram os pedidos.

### 5.1 Threads

Organização sugerida:

1. Thread principal para aceitar conexões.
2. Uma thread receptora para cada processo conectado.
3. Uma thread para executar o algoritmo de exclusão mútua.
4. Uma thread para atender aos comandos do terminal.

As threads receptoras devem colocar as mensagens recebidas em uma `queue.Queue`. A thread do algoritmo consome essa fila e altera o estado do coordenador.

### 5.2 Tratamento de `REQUEST`

```text
adicionar o PID ao final da fila de pedidos

se a região crítica estiver livre:
    remover o primeiro PID da fila
    marcar esse PID como proprietário
    enviar GRANT para ele
```

### 5.3 Tratamento de `RELEASE`

```text
verificar se o PID é o proprietário atual
marcar a região crítica como livre

se a fila não estiver vazia:
    remover o primeiro PID da fila
    marcar esse PID como proprietário
    enviar GRANT para ele
```

Nunca podem existir dois `GRANT` ativos ao mesmo tempo. Depois de cada `GRANT`, o coordenador deve aguardar o `RELEASE` do mesmo processo.

### 5.4 Sincronização

A fila, o proprietário atual, os contadores e o mapa de sockets são dados compartilhados. Use `threading.Lock` ao acessá-los.

Uma alternativa mais simples é permitir que somente a thread do algoritmo modifique a fila e o proprietário. A interface pode consultar cópias desses dados protegida por lock.

### 5.5 Log

O coordenador deve registrar todas as mensagens enviadas e recebidas, incluindo:

- instante com milissegundos;
- direção: enviada ou recebida;
- tipo da mensagem;
- processo de origem ou destino.

Exemplo:

```text
2026-06-22 14:10:32.152 | RECEBIDA | REQUEST | processo=3
2026-06-22 14:10:32.153 | ENVIADA  | GRANT   | processo=3
2026-06-22 14:10:34.154 | RECEBIDA | RELEASE | processo=3
```

### 5.6 Interface do terminal

Implementar os seguintes comandos:

```text
1 - Imprimir a fila atual de pedidos
2 - Imprimir quantas vezes cada processo foi atendido
3 - Encerrar a execução
```

Ao encerrar:

- sinalizar o término das threads;
- fechar os sockets dos processos;
- fechar o socket servidor;
- finalizar o arquivo de log.

## 6. Processo cliente

Parâmetros sugeridos:

```text
processo.py PID IP PORTA R K
```

Exemplo:

```powershell
python processo.py 3 127.0.0.1 5000 10 2
```

Nesse exemplo, o processo de PID `3` executa `10` repetições e permanece `2` segundos na região crítica.

### Fluxo do processo

```text
conectar ao coordenador

repetir r vezes:
    enviar REQUEST
    aguardar GRANT

    abrir resultado.txt em modo append
    escrever PID e horário com milissegundos
    fechar resultado.txt
    aguardar k segundos

    enviar RELEASE

fechar o socket
```

Exemplo de linha em `resultado.txt`:

```text
3 | 2026-06-22 14:10:32.153
```

De acordo com o enunciado, o `sleep(k)` faz parte da região crítica. Portanto, o `RELEASE` deve ser enviado somente depois dele.

## 7. Inicializador dos processos

O `launcher.py` deve receber `n`, `r` e `k`:

```text
launcher.py N R K
```

Responsabilidades:

1. Esvaziar `resultado.txt` antes do teste.
2. Criar os processos sequencialmente e sem atraso proposital.
3. Usar `subprocess.Popen` para permitir execução concorrente.
4. Aguardar a finalização de todos os processos.

## 8. Ordem de implementação

- [ ] Criar `protocolo.py`.
- [ ] Testar a criação de mensagens com exatamente `F` bytes.
- [ ] Implementar `receber_exatamente`.
- [ ] Criar um coordenador simples para um processo.
- [ ] Criar `processo.py`.
- [ ] Testar o ciclo `REQUEST → GRANT → RELEASE`.
- [ ] Adicionar a fila FIFO.
- [ ] Permitir vários processos conectados.
- [ ] Adicionar as threads e a sincronização.
- [ ] Adicionar o log.
- [ ] Implementar a interface do terminal.
- [ ] Criar `launcher.py`.
- [ ] Criar `analisar.py`.
- [ ] Executar os estudos de caso.
- [ ] Escrever o relatório.
- [ ] Preparar a apresentação.

## 9. Validação automática

O `analisar.py` deve verificar:

- `resultado.txt` possui exatamente `n × r` linhas;
- cada PID aparece exatamente `r` vezes;
- os horários estão em ordem crescente;
- todo `GRANT` possui um `RELEASE` correspondente;
- `GRANT` e `RELEASE` aparecem intercalados;
- o PID do `RELEASE` é o proprietário atual;
- a ordem FIFO dos pedidos foi respeitada;
- nunca existiram dois processos simultaneamente na região crítica.

## 10. Estudos de caso

Executar pelo menos três cenários:

| Caso | n | r | k | Objetivo |
|---|---:|---:|---:|---|
| Pequeno | 2 | 3 | 1 | Conferência manual |
| Médio | 5 | 10 | 1 | Testar concorrência |
| Intenso | 10 | 20 | 0,1 ou 1 | Testar fila e carga |

Para cada teste, registrar:

- quantidade esperada e obtida de linhas;
- quantidade de atendimentos por processo;
- tempo total de execução;
- violações encontradas pelo analisador;
- trechos relevantes do log.

## 11. Relatório de até 6 páginas

Estrutura sugerida:

1. Introdução e objetivo.
2. Arquitetura do sistema.
3. Protocolo e formato das mensagens.
4. Coordenador, threads, fila e sincronização.
5. Processo e região crítica.
6. Metodologia dos testes.
7. Resultados e avaliação.
8. Conclusão.

Incluir um diagrama da arquitetura e uma tabela resumindo os estudos de caso.

## 12. Apresentação de até 6 minutos

Sugestão de divisão do tempo:

| Parte | Tempo aproximado |
|---|---:|
| Problema e objetivo | 40 segundos |
| Arquitetura | 60 segundos |
| Protocolo | 60 segundos |
| Algoritmo do coordenador | 90 segundos |
| Demonstração | 60 segundos |
| Testes e resultados | 60 segundos |
| Conclusão | 30 segundos |

## 13. Pontos de atenção

- Não assumir que um único `recv` recebe uma mensagem inteira.
- Garantir que toda mensagem tenha exatamente `F` bytes.
- Não enviar um novo `GRANT` enquanto a região crítica estiver ocupada.
- Verificar se o `RELEASE` pertence ao processo atualmente autorizado.
- Proteger todos os estados compartilhados entre threads.
- Manter o acesso em ordem FIFO.
- Enviar `RELEASE` somente depois do `sleep(k)`.
- Confirmar que o arquivo final possui exatamente `n × r` linhas.
