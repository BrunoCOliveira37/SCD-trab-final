# Verificação da implementação e instruções de execução

Este arquivo registra a revisão da implementação atual, sem modificar os arquivos `.py`.

Arquivos analisados:

- `protocolo.py`
- `coordenador.py`
- `processo.py`
- `launcher.py`
- `analisar.py`

## Resumo geral

A implementação está bem encaminhada e segue a ideia central pedida no trabalho:

- há um coordenador centralizado;
- os processos clientes se conectam ao coordenador por socket TCP;
- existem mensagens fixas de tamanho `F`;
- as mensagens usam os três tipos exigidos: `REQUEST`, `GRANT` e `RELEASE`;
- o processo só escreve no `resultado.txt` depois de receber `GRANT`;
- o coordenador mantém fila de pedidos;
- o coordenador registra log de mensagens recebidas e enviadas;
- existe interface por terminal com comandos para fila, atendimentos e encerramento;
- existe um `launcher.py` para iniciar vários processos sem atraso proposital;
- existe um `analisar.py` para validar o resultado.

Ou seja: a arquitetura principal está compatível com o enunciado.

## Pontos corretos

### 1. Protocolo de mensagens

No `protocolo.py`, as mensagens possuem tamanho fixo:

```python
F = 32
```

Os tipos também estão corretos:

```python
REQUEST = 1
GRANT = 2
RELEASE = 3
```

A função `criar_mensagem` gera mensagens com separador `|` e preenche com zeros até completar `F` bytes. Isso atende à exigência do PDF.

Exemplo lógico de mensagem:

```text
1|3|0000000000000000000000000000
```

### 2. Coordenador centralizado

O `coordenador.py` implementa um coordenador com múltiplas threads:

- uma thread aceita conexões;
- uma thread processa eventos do algoritmo;
- uma thread lê comandos do terminal;
- há uma thread receptora para cada processo conectado.

Isso atende à exigência de o coordenador ser multithread.

### 3. Fila de pedidos

O coordenador usa:

```python
self.fila_pedidos: Deque[int] = deque()
```

Essa fila armazena os processos que pediram acesso à região crítica.

### 4. Exclusão mútua

O controle principal é feito por:

```python
self.processo_na_regiao_critica
```

Quando há um processo dentro da região crítica, outro `GRANT` não é enviado. Quando chega um `RELEASE`, o coordenador libera o estado e tenta atender o próximo processo.

Essa lógica está correta para exclusão mútua centralizada.

### 5. Processo cliente

O `processo.py` segue o fluxo correto:

1. conecta no coordenador;
2. envia `REQUEST`;
3. espera `GRANT`;
4. escreve no `resultado.txt`;
5. dorme `k` segundos;
6. envia `RELEASE`;
7. repete isso `r` vezes.

Isso está de acordo com o enunciado.

### 6. Inicialização dos processos

O `launcher.py` inicia os processos em sequência, sem atraso artificial:

```python
for pid in range(1, args.n + 1):
    subprocess.Popen(...)
```

Também limpa o `resultado.txt` antes da execução, o que ajuda na validação.

## Mudanças necessárias ou recomendadas

### Mudança 1: corrigir a validação do log em `analisar.py`

Este é o ponto mais importante.

No coordenador, o log registra:

- `REQUEST` como `RECEBIDA`;
- `GRANT` como `ENVIADA`;
- `RELEASE` como `RECEBIDA`.

Isso faz sentido, porque:

- o processo envia `REQUEST` ao coordenador;
- o coordenador envia `GRANT` ao processo;
- o processo envia `RELEASE` ao coordenador.

Porém, no `analisar.py`, a função `validar_log` atualmente considera apenas eventos com:

```python
if evento.direcao != "ENVIADA":
    continue
```

Com isso, ela ignora os `REQUEST` e `RELEASE`, porque eles aparecem no log como `RECEBIDA`.

Resultado: o validador pode acusar erro mesmo se o algoritmo estiver funcionando corretamente.

#### Como deveria ser a lógica

O analisador deveria considerar:

- `RECEBIDA REQUEST` para montar a ordem dos pedidos;
- `ENVIADA GRANT` para saber quem recebeu permissão;
- `RECEBIDA RELEASE` para saber quem saiu da região crítica.

Uma correção conceitual seria:

```python
if evento.direcao == "RECEBIDA" and evento.tipo == "REQUEST":
    requests.append(evento.pid)

elif evento.direcao == "ENVIADA" and evento.tipo == "GRANT":
    grants.append(evento.pid)
    owner = evento.pid

elif evento.direcao == "RECEBIDA" and evento.tipo == "RELEASE":
    releases.append(evento.pid)
    owner = None
```

Depois, validar:

```python
requests == releases
grants == releases
```

Essa mudança é recomendada antes de usar o `analisar.py` como prova final da corretude.

### Mudança 2: limpar o log a cada nova execução

No `coordenador.py`, o arquivo de log é aberto assim:

```python
self.arquivo_log = open(self.log_path, "a", encoding="utf-8", buffering=1)
```

O modo `"a"` significa append, ou seja, o log antigo não é apagado. Isso pode atrapalhar a análise, porque execuções anteriores ficam misturadas com a execução atual.

Recomendação:

```python
self.arquivo_log = open(self.log_path, "w", encoding="utf-8", buffering=1)
```

O modo `"w"` recria o log a cada execução do coordenador.

Alternativa: manter `"a"`, mas apagar manualmente `coordenador.log` antes de cada teste.

### Mudança 3: cuidado com a interface do coordenador

O coordenador espera comandos digitados no terminal:

```text
1
2
3
```

Significado:

- `1`: imprime a fila atual;
- `2`: imprime quantas vezes cada processo foi atendido;
- `3`: encerra o coordenador.

Isso atende ao enunciado, mas significa que o coordenador deve ficar aberto em um terminal separado enquanto os processos rodam.

## Como rodar

Abra um terminal na pasta do projeto:

```powershell
cd "C:\Users\bruno\OneDrive\Área de Trabalho\SCD\trab_final"
```

### 1. Iniciar o coordenador

No primeiro terminal:

```powershell
python coordenador.py --host 127.0.0.1 --port 5000
```

Deixe esse terminal aberto.

Se quiser consultar a fila durante a execução, digite:

```text
1
```

Se quiser ver quantas vezes cada processo foi atendido:

```text
2
```

Para encerrar o coordenador:

```text
3
```

### 2. Iniciar os processos

Abra um segundo terminal na mesma pasta.

Exemplo pequeno:

```powershell
python launcher.py 3 5 1
```

Significado:

- `3`: número de processos;
- `5`: número de repetições por processo;
- `1`: tempo `k`, em segundos, que o processo dorme após escrever no arquivo.

Esse teste deve gerar:

```text
3 * 5 = 15 linhas
```

no arquivo `resultado.txt`.

### 3. Validar o resultado

Depois que o `launcher.py` terminar, rode:

```powershell
python analisar.py 3 5
```

Se estiver tudo certo, o ideal é aparecer:

```text
Validacao concluida sem violacoes
```

Mas atenção: antes de confiar no `analisar.py`, aplique a correção descrita na seção “Mudança 1”, porque a versão atual tende a validar o log de forma incorreta.

## Sugestão de testes para o relatório

Use pelo menos três cenários:

### Teste 1: pequeno

```powershell
python launcher.py 2 3 1
python analisar.py 2 3
```

Resultado esperado:

```text
6 linhas em resultado.txt
```

### Teste 2: médio

```powershell
python launcher.py 5 10 1
python analisar.py 5 10
```

Resultado esperado:

```text
50 linhas em resultado.txt
```

### Teste 3: maior

```powershell
python launcher.py 10 20 0.2
python analisar.py 10 20
```

Resultado esperado:

```text
200 linhas em resultado.txt
```

## Ordem recomendada para apresentar na prova

Na apresentação, explique nesta ordem:

1. O problema: vários processos querem escrever no mesmo arquivo.
2. A solução: coordenador centralizado controlando a região crítica.
3. As mensagens: `REQUEST`, `GRANT` e `RELEASE`.
4. O fluxo:
   - processo pede acesso;
   - coordenador coloca na fila;
   - coordenador libera um por vez;
   - processo escreve no arquivo;
   - processo avisa que saiu.
5. A validação:
   - `resultado.txt` tem `n * r` linhas;
   - cada processo aparece `r` vezes;
   - os horários estão em ordem;
   - no log, cada `GRANT` é seguido por um `RELEASE`.

## Conclusão

A implementação está conceitualmente correta e bem próxima do que o trabalho pede.

Antes da entrega, eu recomendo principalmente:

1. corrigir a análise do log em `analisar.py`;
2. limpar o `coordenador.log` a cada execução, seja manualmente ou abrindo o arquivo em modo `"w"`;
3. rodar os três testes sugeridos;
4. salvar os resultados para usar no relatório.

