# ADEDONALD — Jogo de Adedonha Online

ADEDONALD é um jogo multiplayer de adedonha implementado em Python utilizando a biblioteca RPyC para comunicação em rede transparente e uma interface interativa em linha de comando (CLI) via terminal.

## Requisitos

- Python 3.10+
- RPyC

## Instalação do Cliente e do Servidor

Instale as dependências do cliente e do servidor executando o comando abaixo:

```bash
source setup.sh
```

## Como Executar

### 1. Iniciar o Servidor

Em um terminal, execute:

```bash
./server_run.sh
```

O servidor será iniciado na porta `18861`.

### 2. Iniciar os Clientes

Em outros terminais (são necessários pelo menos 2 jogadores para iniciar uma partida), execute:

```bash
./client_run.sh
```

Siga as instruções na tela para conectar-se ao servidor (padrão: `localhost`), definir seu nickname e criar ou entrar em uma sala.
