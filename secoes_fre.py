"""Mapa entre as tags do XML do Formulário de Referência (CVM) e o número da seção.

O download da CVM devolve um ZIP com o formulário em XML. Cada seção narrativa
vem como um PDF embutido em base64:

    <DescricaoFatoresRisco>
      <NomeArquivoPdf>qualquer-nome.pdf</NomeArquivoPdf>
      <ImagemObjetoArquivoPdf>JVBERi0...</ImagemObjetoArquivoPdf>
    </DescricaoFatoresRisco>

O nome do arquivo é livre (cada empresa escreve o que quer), mas a tag é fixa.
Mapa levantado em 27/10/2026 a partir de três formulários de 2025
(Bradesco v30, Panatlântica v4, Bioma Educação v10), estrutura vigente desde 2023.
"""

TAG_SECAO = {
    "HistoricoEmissor": ("1.1", "Histórico do emissor"),
    "AtividadesEmissorControladas": ("1.2", "Principais atividades"),
    "InfoSegmentosOperacionais": ("1.3", "Segmentos operacionais"),
    "ProducaoComercializacaoMercados": ("1.4", "Produção, comercialização e mercados"),
    "PrincipaisClientes": ("1.5", "Principais clientes"),
    "EfeitosRegulacaoEstatal": ("1.6", "Efeitos da regulação estatal"),
    "ReceitasRelevantes": ("1.7", "Receitas relevantes"),
    "EfeitosRegulacaoEstrangeira": ("1.8", "Efeitos de regulação estrangeira"),
    "InfoASG": ("1.9", "Informações ASG"),
    "InfoSociedadeEconomiaMista": ("1.10", "Sociedade de economia mista"),
    "AtivoRelevante": ("1.11", "Aquisição ou alienação de ativo relevante"),
    "OperacoesSocietarias": ("1.12", "Operações societárias"),
    "AcordosAcionistas": ("1.13", "Acordos de acionistas"),
    "AlteracoesNegocios": ("1.14", "Alterações significativas na condução dos negócios"),
    "ContratosRelevantes": ("1.15", "Contratos relevantes"),
    "OutrasInfoRelevantes": ("1.16", "Outras informações relevantes"),
    "CondicoesFinanceirasPatrimoniais": ("2.1", "Condições financeiras e patrimoniais"),
    "ResultadosOperFinanceiros": ("2.2", "Resultados operacional e financeiro"),
    "MudancasPraticasContabeis": ("2.3", "Mudanças nas práticas contábeis"),
    "EfeitosRelevantesDF": ("2.4", "Efeitos relevantes nas DFs"),
    "MedicoesNaoContabeis": ("2.5", "Medições não contábeis"),
    "EventosSubsequentesDF": ("2.6", "Eventos subsequentes"),
    "DestinacaoResultados": ("2.7", "Destinação de resultados"),
    "ItensRelevantesNaoEvidenciadosDF": ("2.8", "Itens não evidenciados nas DFs"),
    "ComentariosItensNaoEvidenciados": ("2.9", "Comentários sobre itens não evidenciados"),
    "PlanoNegocios": ("2.10", "Planos de negócios"),
    "FatoresInfluenciaDesempenhoOperacional": ("2.11", "Outros fatores do desempenho operacional"),
    "ProjecoesDivulgadasPremissas": ("3.1", "Projeções divulgadas e premissas"),
    "AcompanhamentoProjecoes": ("3.2", "Acompanhamento das projeções"),
    "DescricaoFatoresRisco": ("4.1", "Fatores de risco"),
    "Descricao5PrincipaisFatoresRisco": ("4.2", "Cinco principais fatores de risco"),
    "DescricaoRiscosMercado": ("4.3", "Riscos de mercado"),
    "ProcessosNaoSigilosos": ("4.4", "Processos não sigilosos"),
    "ValorProvisionadoProcessosNaoSigilosos": ("4.5", "Valor provisionado dos processos"),
    "ProcessosSigilosos": ("4.6", "Processos sigilosos"),
    "ContingenciasRelevantes": ("4.7", "Outras contingências"),
    "DescricaoGerenciamentoRiscos": ("5.1", "Gerenciamento de riscos"),
    "DescricaoControlesInternos": ("5.2", "Controles internos"),
    "ProgramaIntegridade": ("5.3", "Programa de integridade"),
    "AlteracoesSignificativas": ("5.4", "Alterações significativas"),
    "OrganogramaAcionistasGrupoEconomico": ("6.5", "Organograma"),
    "CaracteristicasOrgaosAdmECF": ("7.1", "Órgãos de administração"),
    "InformacoesConselhoAdm": ("7.2", "Conselho de administração"),
    "AcordosSegurosAdministradores": ("7.7", "Acordos e seguros de administradores"),
    "PoliticaPraticaRemuneracao": ("8.1", "Política de remuneração"),
    "PlanoRemuneracaoBaseadoAcoes": ("8.4", "Remuneração baseada em ações"),
    "OutorgaOpcoesCompraAcao": ("8.6", "Outorga de opções"),
    "OpcoesAberto": ("8.7", "Opções em aberto"),
    "OpcoesExercidasAcoesEntregues": ("8.8", "Opções exercidas"),
    "RemunBaseadaAcoesASeremEntregues": ("8.9", "Diluição potencial"),
    "OutorgaAcoes": ("8.10", "Outorga de ações"),
    "PrecificacaoAcoesOpcoes": ("8.12", "Precificação das ações e opções"),
    "ParticipacaoDetidaOrgao": ("8.13", "Participações detidas por órgão"),
    "PlanosPrevidencia": ("8.14", "Planos de previdência"),
    "MecanismosRemuneracaoIndenizacao": ("8.16", "Mecanismos de remuneração e indenização"),
    "PercentualPartesRelacionadas": ("8.17", "Partes relacionadas na remuneração"),
    "RemuneracaoOutrasFuncoes": ("8.18", "Remuneração por outras funções"),
    "RemuneracaoReconhecidaControlador": ("8.19", "Remuneração reconhecida do controlador"),
    "IndependConflitoInteresse": ("9.3", "Independência dos auditores"),
    "DescricaoRH": ("10.1", "Recursos humanos"),
    "AlteracoesRelev": ("10.2", "Alterações relevantes (RH)"),
    "RemuneracaoEmpregados": ("10.3", "Remuneração dos empregados"),
    "RelacaoEmissorSindicato": ("10.4", "Relações com sindicatos"),
    "RegrasPoliticasPraticas": ("11.1", "Partes relacionadas: regras"),
    "OutrasInfRelevNO": ("11.2", "Partes relacionadas: itens n e o"),
    "EmissoresEstrangeiros": ("12.2", "Emissores estrangeiros"),
    "MercadosNegociacaoBR": ("12.5", "Mercados de negociação no Brasil"),
    "DestinacaoRecursosOfertasPublicas": ("12.8", "Destinação de recursos de ofertas"),
    "DeclaracaoDiretorPresidente": ("13.1", "Declaração do diretor presidente"),
    "DeclaracaoDiretorRelacoes": ("13.1", "Declaração do DRI"),
    "DeclaracaoDiretorPresidenteRelacoes": ("13.1", "Declaração do diretor presidente e DRI"),
    # variantes com sufixo, vistas em 2025
    "DeclaracaoDiretorPresidente132": ("13.1", "Declaração do diretor presidente"),
    "DeclaracaoDiretorRelacoes132": ("13.1", "Declaração do DRI"),
    "DeclaracaoDiretorPresidenteRelacoes132": ("13.1", "Declaração do diretor presidente e DRI"),
}

# "OutrasInfRelev" aparece uma vez por capítulo: a seção sai do capítulo
# da última tag conhecida antes dela.
OUTRAS_POR_CAPITULO = {
    "5": "5.5", "6": "6.6", "7": "7.8", "8": "8.20",
    "9": "9.4", "10": "10.5", "11": "11.3", "12": "12.9",
}
