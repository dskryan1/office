OFFICE TELCO — PAINEL CENTRAL DE TI (VERSÃO INICIAL)
=====================================================

O QUE ESTA VERSÃO FAZ
- Painel local no navegador.
- Cadastro e atualização manual de chamados.
- Inventário básico do computador local.
- Exportação de chamados e inventário para CSV.
- Consulta opcional e SOMENTE LEITURA ao Active Directory via PowerShell/RSAT.
- Banco SQLite local em dados\office_telco_ti.db.

O QUE NÃO FAZ
- Não altera usuários, grupos ou computadores do AD.
- Não muda configurações do Windows.
- Não acessa ou varre outros computadores da rede.
- Não publica o painel na rede: ele escuta somente 127.0.0.1.

REQUISITOS
- Windows 10/11.
- Python 3.11 ou 3.12 instalado.
- Acesso à internet ou repositório aprovado para instalar dependências Python.
- Para a consulta AD: módulo PowerShell ActiveDirectory/RSAT disponível e conta autorizada.

INSTALAÇÃO
1. Extraia o ZIP para uma pasta local, por exemplo:
   C:\OfficeTelcoTI
2. Instale Python 3.11 ou 3.12 pelo site oficial, se ainda não existir.
   Durante a instalação, marque "Add Python to PATH".
3. Dê dois cliques em Instalar_Painel.bat.
4. Quando terminar, dê dois cliques em Iniciar_Painel.bat.
5. Abra o endereço local que o Streamlit mostrar (normalmente http://127.0.0.1:8501).

PRIMEIRO TESTE SEGURO
1. Abra Visão geral e execute o diagnóstico local.
2. Abra Inventário e confirme que o computador aparece.
3. Cadastre um chamado fictício, por exemplo "TESTE - não encaminhar".
4. Atualize o status e exporte o CSV.
5. Só depois teste o módulo AD, se o RSAT estiver instalado e você tiver autorização.

DADOS E BACKUP
- Banco de dados: pasta dados\office_telco_ti.db
- Para backup consistente, feche o painel e copie a pasta dados para um local aprovado pela empresa.
- O banco fica neste computador. Não compartilhe a pasta em rede sem revisar controles de acesso.

SEGURANÇA
- Não execute como administrador, salvo necessidade aprovada.
- Não coloque senhas em scripts, chamados ou arquivos de configuração.
- A consulta ao AD usa somente comandos de leitura.
- Não abra a porta 8501 no firewall nem altere o endereço para 0.0.0.0 sem revisão de segurança.
- Antes de usar dados reais, confirme a autorização da Office Telco para registrar informações no banco local.
- Esta versão é um protótipo interno; não substitui um sistema de chamados com autenticação, trilha de auditoria e backup corporativo.

SOLUÇÃO DE PROBLEMAS
- "Python não encontrado": reinstale Python e marque Add Python to PATH.
- Falha de instalação de pacotes: verifique proxy/firewall ou use o repositório aprovado pela empresa.
- AD não disponível: abra PowerShell e rode:
    Get-Module -ListAvailable ActiveDirectory
  Se não retornar nada, o módulo RSAT pode não estar instalado. Peça validação ao administrador responsável.
- Para parar o painel: feche a janela preta do Iniciar_Painel.bat.
