# ADEDONALD — Jogo de Adedonha Online

ADEDONALD é um jogo multiplayer de adedonha implementado em Python utilizando a biblioteca RPyC para comunicação em rede transparente e uma interface interativa em linha de comando (CLI) via terminal.

## Requisitos

- Python 3.10+
- RPyC

## Instalação

Instale as dependências executando o comando abaixo:

```bash
pip install -r requirements.txt
```

## Como Executar

### 1. Iniciar o Servidor

Em um terminal, execute:

```bash
python -m server.main
```

O servidor será iniciado na porta `18861`.

### 2. Iniciar os Clientes

Em outros terminais (são necessários pelo menos 2 jogadores para iniciar uma partida), execute:

```bash
python -m client.main
```

Siga as instruções na tela para conectar-se ao servidor (padrão: `localhost`), definir seu nickname e criar ou entrar em uma sala.

## Testes

Para executar as validações de unidade automáticas:

```bash
python -m unittest test_game.py
```
