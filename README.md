# Cybersecurity Error Lab

Aplicação Flask para experimento acadêmico com consentimento explícito.

## Funcionalidades
- Página de simulação 404 com aviso de privacidade.
- Registro, após consentimento, de IP observado pelo servidor, horário UTC,
  User-Agent, idioma e resolução/tamanho da tela informado pelo navegador.
- Consulta de geolocalização aproximada por IP via ipwho.is, sem solicitar GPS.
- Mapa Leaflet/OpenStreetMap no painel com marcadores dos acessos geolocalizados.
- Envio manual e voluntário de captura de tela.
- Painel administrativo com senha, exportação CSV e exclusão de registros.
- Cabeçalhos básicos de segurança.

## Limitações importantes
- A localização é uma estimativa por IP via ipwho.is. O IP é enviado a esse
  terceiro para consulta; isso deve ser informado ao participante e avaliado
  no protocolo de privacidade/LGPD. Consulte os termos, limites e política do
  provedor antes de uso acadêmico. O resultado não é endereço exato nem GPS.
- O servidor não confia em `X-Forwarded-For` por padrão. Em hospedagem atrás de
  proxy, configure explicitamente o proxy confiável antes de usar o IP encaminhado.
- SQLite e arquivos locais exigem armazenamento persistente. Algumas hospedagens
  gratuitas apagam arquivos locais ou suspendem aplicações; confirme as regras
  do provedor antes de usar com dados reais.
- Não há proteção anti-abuso avançada, gestão de usuários, rotação de logs ou
  política automática de expurgo. Use apenas em ambiente controlado e com poucos
  participantes autorizados até implementar esses controles.

## Executar localmente
1. Python 3.11 ou superior.
2. `python -m venv .venv`
3. Ative o ambiente virtual.
4. `pip install -r requirements.txt`
5. Defina `SECRET_KEY` e `ADMIN_PASSWORD` no ambiente.
6. `python app.py`
7. Acesse `http://127.0.0.1:5000` e o painel em `/admin`.

Exemplo no PowerShell:
```powershell
$env:SECRET_KEY="uma-chave-aleatoria-longa"
$env:ADMIN_PASSWORD="uma-senha-forte"
python app.py
```

## Publicação
O projeto inclui `Procfile` para provedores que aceitam aplicações Python/Gunicorn.
Na publicação:
- Configure `SECRET_KEY` e `ADMIN_PASSWORD` como variáveis secretas do serviço.
- Ative HTTPS e `COOKIE_SECURE=1`.
- Configure armazenamento persistente para banco e uploads, se o provedor oferecer.
- Restrinja o painel `/admin` e não compartilhe a senha.
- Teste exclusão de dados, backup e restauração antes do experimento.

## Ética, privacidade e LGPD
Use somente com participantes informados e consentimento livre, específico e revogável.
Defina finalidade, base legal, prazo de retenção, canal de contato e procedimento de
exclusão. Colete o mínimo necessário. Não tente identificar residência, pessoa ou
localização precisa a partir do IP. Não faça captura de tela automática ou oculta.
Para pesquisa institucional, valide o protocolo com orientador/comitê responsável.


## Publicação simplificada no Render (protótipo gratuito)

O repositório inclui `render.yaml` para criar um Web Service gratuito via Blueprint.
1. Crie um repositório no GitHub e envie o conteúdo desta pasta (não envie `.env`, banco local ou `uploads/`).
2. No Render, selecione **New → Blueprint** e conecte o repositório.
3. Confira o serviço `cybersecurity-error-lab`.
4. Quando solicitado, defina `ADMIN_PASSWORD` como uma senha longa e exclusiva.
5. Clique em aplicar/criar. O Render fará o build e fornecerá um endereço `*.onrender.com`.
6. Teste `/health`, a página inicial e `/admin`.

### Limitação crítica do plano gratuito

Este Blueprint usa SQLite e arquivos em `/tmp` para permitir uma demonstração inicial. No Render Free, o sistema de arquivos é efêmero: banco e capturas podem ser apagados em reinícios, suspensão ou novo deploy. O serviço também pode suspender após 15 minutos sem tráfego e demorar cerca de um minuto para voltar. Portanto, use esta configuração somente para demonstração e testes sem dados de pesquisa importantes.

Para uma coleta de tese que precise preservar evidências, migre antes para armazenamento persistente (por exemplo, Render Postgres para registros e armazenamento de objetos para capturas) ou use serviço pago com disco persistente. O Postgres gratuito do Render também expira após 30 dias, portanto não deve ser tratado como arquivo permanente.

### IP atrás do proxy

A aplicação usa `ProxyFix` configurado para um único proxy reverso, para que o IP encaminhado pelo Render seja interpretado como IP do visitante. Não altere essa contagem sem confirmar a cadeia real de proxies; confiar em cabeçalhos encaminhados arbitrários pode permitir falsificação de IP.

### Segurança e pesquisa

- O painel `/admin` deve usar senha forte e não compartilhada.
- A página informa que o IP é enviado ao serviço IPWho.is para estimativa geográfica.
- IP e geolocalização aproximada continuam sendo dados pessoais; defina finalidade, base legal, retenção, canal de contato e procedimento de exclusão conforme orientação institucional e LGPD.
- Não use o modo gratuito para guardar evidências essenciais da pesquisa.
