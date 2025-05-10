
# ANSK IRC Download Bot

Este projeto é um bot automatizado que conecta-se ao servidor IRC do [AnskTracker](https://www.ansktracker.com/) `e que pode ser facilmente ajustado para ser utilizado em outros servidores IRC` e realiza o download de todos os animes/arquivos disponíveis nos bots presentes no servidor.

### `Esse é um projeto meramente com o intúito educacional, não tenho qualquer relação com o site, servidor IRC ou seus membros.` 

## 📦 Funcionalidades

- Conexão automática ao servidor IRC do Ansk Tracker.
- Listagem e identificação de bots ativos no canal.
- Envio automático de comandos de download (XDCC SEND).
- Armazenamento local dos arquivos recebidos.
- Registro dos arquivos baixados para evitar duplicatas.
- Possibilidade de baixar arquivos específicos de um bot.

## 🧩 Dependência: `xdcc_download_server`

Este projeto depende de um serviço auxiliar chamado `xdcc_download_server`, que é responsável por:

- Manter uma conexão com o servidor IRC (como o `irc.rizon.net`);
- Ingressar no canal específico (`#AnimeNSK`);
- Receber e responder comandos de download enviados via socket TCP;
- Fazer o download dos pacotes (animes/arquivos) solicitados via protocolo XDCC;
- Armazenar os arquivos no volume compartilhado `/data`.

O `ansk_client.py` não faz o download diretamente, mas se comunica com este serviço enviando comandos via socket. O `xdcc_download_server` então executa o processo de download no IRC e salva os arquivos.

A comunicação ocorre via um protocolo JSON simples enviado para a porta 8080 do serviço. Um exemplo de payload enviado pelo cliente:

```json
{
  "bot_name": "ANSK|Kuroneko",
  "pack_number": "123",
  "send_progress": true,
  "download_path": "Kuroneko"
}
```

O `xdcc_download_server` responde com mensagens de progresso, sucesso ou erro.

## 🚀 Tecnologias Utilizadas

- Python 3
- IRC (protocolo de comunicação)
- Bibliotecas: `requests`, `beautifulsoup4`, `pandas`

## 📁 Estrutura do Projeto

```
.
├── ansk_client.py          # Código principal do bot que acessa o IRC
├── requirements.txt        # Dependências Python do projeto
```

## ▶️ Como Usar
O script irá varrer e catalogar e enfileirar para download todos os arquivos disponíveis nos bots e não presentes no seu diretório de download.

#### Docker:
```bash
sudo docker compose up > logs/`date +\%Y\%m\%d\%H\%M\%S`_downloads.log
```

### Agendamento no Crontab para atualização diária:
```bash
0 8 * * * /usr/local/bin/docker-compose -f /path/to/the/project_folder/docker-compose.yml up > /path/to/the/project_folder/logs/`date +%Y%m%d%H%M%S`_downloads.log 2>&1
```

O script irá automaticamente:

1. Acessar a página de listagem de pacotes do Ansk Tracker.
2. Identificar os bots disponíveis e os arquivos ainda não baixados.
3. Conectar-se ao servidor IRC por meio do `xdcc_download_server`.
4. Solicitar os downloads via XDCC SEND.
5. Registrar o progresso e os arquivos baixados para evitar duplicatas futuras.

## 🎯 Executando com Filtro Específico

Você pode restringir a execução para baixar arquivos específicos de um bot utilizando variáveis de ambiente:
> O script irá apenas baixar os arquivos indicados, sem verificar ou registrar progresso.

#### CLI:
```bash
sudo BOT="ANSK|Kuroneko" IDS="123,124,125" python3 ansk_client.py
```
#### Docker:
```bash
sudo IDS="1571,1574" BOT="ANSK|Sora" docker compose up > logs/`date +\%Y\%m\%d\%H\%M\%S`_downloads.log
```

- `BOT`: Nome completo do bot (por exemplo: `ANSK|Kuroneko`)
- `IDS`: Lista separada por vírgula com os IDs dos pacotes desejados


## ⏹️ Como Parar

Pressione `CTRL+C` para interromper a execução a qualquer momento com segurança.

## 📌 Notas

- Os arquivos são salvos por padrão no diretório `/data/<nome_do_bot>/`.
- O script mantém um arquivo `log.txt` para cada bot, indicando o último pacote baixado com sucesso.
- A verificação de arquivos já existentes é feita com base no nome/ID do pacote (hash ou extensão `.rar`).

---

**Licença:** Este projeto está sob a licença MIT.
