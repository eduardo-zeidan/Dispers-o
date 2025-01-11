from flask import Flask, render_template, request, send_file
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf
import datetime
import io
from matplotlib.backends.backend_pdf import PdfPages
import warnings

warnings.filterwarnings('ignore')

app = Flask(__name__)

# =========================
# 1) Declaração das carteiras
# =========================
moedas = [
    'USDBRL=X', 'THB=X', 'USDAUD=X', 'USDMXN=X', 'USDGBP=X',
    'USDEUR=X', 'JPY=X', 'CHF=X', 'CAD=X', 'CNY=X', 'INR=X',
    'CZK=X', 'TRY=X', 'NOK=X', 'SEK=X'
]
nomes_amigaveis_moedas = {
    'USDBRL=X': 'Real',
    'THB=X': 'Baht Tailandês',
    'USDAUD=X': 'Dólar Australiano',
    'USDMXN=X': 'Peso Mexicano',
    'USDGBP=X': 'Dólar X Libra',
    'USDEUR=X': 'Dólar X Euro',
    'JPY=X': 'Iene Japonês',
    'CHF=X': 'Franco Suíço',
    'CAD=X': 'Dólar Canadense',
    'CNY=X': 'Yuan Chinês',
    'INR=X': 'Rupia Indiana',
    'CZK=X': 'Coroa Tcheca',
    'TRY=X': 'Lira Turca',
    'NOK=X': 'Coroa Norueguesa',
    'SEK=X': 'Coroa Sueca'
}

bolsas = [
    '^GSPC', '^DJI', '^IXIC', '^FTSE', '^N225', '^GDAXI',
    '^HSI', '^BSESN', '^BVSP', '^MERV', '^FCHI', '^BFX',
    '^TWII', '^STOXX50E', '^TA125.TA', '000001.SS'
]
nomes_amigaveis_bolsas = {
    '^GSPC': 'S&P 500',
    '^DJI': 'Dow Jones',
    '^IXIC': 'Nasdaq',
    '^FTSE': 'FTSE 100',
    '^N225': 'Nikkei 225',
    '^GDAXI': 'DAX',
    '^HSI': 'Hang Seng',
    '^BSESN': 'Sensex (Índia)',
    '^BVSP': 'Bovespa',
    '^MERV': 'Merval (Argentina)',
    '^FCHI': 'CAC 40 (França)',
    '^BFX': 'BEL 20 (Bélgica)',
    '^TWII': 'TSEC (Taiwan)',
    '^STOXX50E': 'Euro Stoxx 50',
    '^TA125.TA': 'TA-125 (Israel)',
    '000001.SS': 'Xangai (China)'
}

commodities = [
    'CL=F', 'GC=F', 'SI=F', 'HG=F', 'NG=F', 'ZC=F', 'ZW=F',
    'KC=F', 'CT=F', 'SB=F', 'PA=F', 'PL=F', 'HO=F', 'RB=F',
    'OJ=F', 'CC=F', 'ZS=F', 'ZM=F', 'LE=F', 'HE=F', 'BZ=F',
    'TIO=F'
]
nomes_amigaveis_commodities = {
    'CL=F': 'Petróleo WTI',
    'GC=F': 'Ouro',
    'SI=F': 'Prata',
    'HG=F': 'Cobre',
    'NG=F': 'Gás Natural',
    'ZC=F': 'Milho',
    'ZW=F': 'Trigo',
    'KC=F': 'Café',
    'CT=F': 'Algodão',
    'SB=F': 'Açúcar',
    'PA=F': 'Paládio',
    'PL=F': 'Platina',
    'HO=F': 'Óleo de Aquecimento',
    'RB=F': 'Gasolina',
    'OJ=F': 'Suco de Laranja',
    'CC=F': 'Cacau',
    'ZS=F': 'Soja (CBOT)',
    'ZM=F': 'Farelo de Soja',
    'LE=F': 'Boi Gordo',
    'HE=F': 'Suínos Magros',
    'BZ=F': 'Petróleo Brent',
    'TIO=F': 'Minério de Ferro'
}

# Unindo todas as carteiras
ativos = moedas + bolsas + commodities

nomes_amigaveis = {
    **nomes_amigaveis_moedas,
    **nomes_amigaveis_bolsas,
    **nomes_amigaveis_commodities
}

# =========================
# 2) Funções auxiliares
# =========================
def ajustar_timezone(index):
    if hasattr(index, 'tz'):
        return index.tz_convert(None)
    return index

def verificar_dados_inconsistentes(dados):
    """Remove NaN e zeros (se for o caso) para evitar problemas."""
    if dados.isnull().any().any():
        dados = dados.dropna()
    if (dados == 0).any().any():
        dados = dados[dados != 0]
    return dados

def obter_fechamento_exato(historico, datas):
    """
    Pega o fechamento exato para as datas em 'datas'.
    Se não existir valor exato naquele dia, usa asof(data).
    """
    preços = {}
    for nome_periodo, data in datas.items():
        if data in historico.index:
            preços[nome_periodo] = historico['Close'].loc[data]
        else:
            # asof pega a cotação mais próxima anterior à data
            preços[nome_periodo] = historico['Close'].asof(data)
    return preços

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/gerar", methods=["POST"])
def gerar_pdf():
    # =========================
    # 3) Obter dados e montar DF
    # =========================
    hoje = datetime.datetime.now().replace(tzinfo=None)
    inicio_ano = datetime.datetime(2025, 1, 1).replace(tzinfo=None)
    periodos = {
        '7d': (hoje - pd.offsets.BDay(7)).replace(tzinfo=None),
        '45d': (hoje - pd.offsets.BDay(45)).replace(tzinfo=None),
        '90d': (hoje - pd.offsets.BDay(90)).replace(tzinfo=None),
        '1y': inicio_ano  # variação "Anual" a partir de 2025-01-01
    }

    # Dicionário para armazenar as variações
    variacoes = {
        'Ativo': [],
        'Nome_Amigavel': [],
        'Classe': [],
        'Variação_Anual': [],
        'Variação_7_Dias': [],
        'Variação_45_Dias': [],
        'Variação_90_Dias': []
    }

    # Coletar desde 2024
    inicio_dados = datetime.datetime(2024, 1, 1).replace(tzinfo=None)

    for ativo in ativos:
        classe = 'Moeda' if ativo in moedas else ('Bolsa' if ativo in bolsas else 'Commodity')
        nome_amigavel = nomes_amigaveis.get(ativo, ativo)

        ticker = yf.Ticker(ativo)
        historico = ticker.history(start=inicio_dados, end=hoje)

        # Ajustar o index para remover timezone
        historico.index = ajustar_timezone(historico.index)

        if not historico.empty:
            # Limpar dados inconsistentes
            historico = verificar_dados_inconsistentes(historico)

            try:
                # Dados desde 2025 para calcular variação anual
                historico_2025 = historico[historico.index >= inicio_ano]
                if not historico_2025.empty:
                    preco_atual = historico_2025['Close'].iloc[-1]
                    preco_inicio_2025 = historico_2025['Close'].iloc[0]
                    variacao_anual = ((preco_atual - preco_inicio_2025) / preco_inicio_2025) * 100
                else:
                    # Se não tiver dados em 2025, coloca None
                    variacao_anual = None
                    preco_atual = historico['Close'].iloc[-1]  # para uso nos períodos
                # Obter fechamentos exatos
                precos = obter_fechamento_exato(historico, periodos)

                def pct_diff(recente, antigo):
                    if antigo is not None and antigo != 0:
                        return ((recente - antigo) / antigo) * 100
                    return None

                variacao_7_dias = pct_diff(preco_atual, precos['7d'])
                variacao_45_dias = pct_diff(preco_atual, precos['45d'])
                variacao_90_dias = pct_diff(preco_atual, precos['90d'])

                variacoes['Ativo'].append(ativo)
                variacoes['Nome_Amigavel'].append(nome_amigavel)
                variacoes['Classe'].append(classe)
                variacoes['Variação_Anual'].append(variacao_anual)
                variacoes['Variação_7_Dias'].append(variacao_7_dias)
                variacoes['Variação_45_Dias'].append(variacao_45_dias)
                variacoes['Variação_90_Dias'].append(variacao_90_dias)

            except Exception as e:
                print(f"Erro ao processar {nome_amigavel}: {e}")
                # Se algo falhar, ainda adicionamos a linha, mas com None
                variacoes['Ativo'].append(ativo)
                variacoes['Nome_Amigavel'].append(nome_amigavel)
                variacoes['Classe'].append(classe)
                variacoes['Variação_Anual'].append(None)
                variacoes['Variação_7_Dias'].append(None)
                variacoes['Variação_45_Dias'].append(None)
                variacoes['Variação_90_Dias'].append(None)
        else:
            # histórico vazio
            variacoes['Ativo'].append(ativo)
            variacoes['Nome_Amigavel'].append(nome_amigavel)
            variacoes['Classe'].append(classe)
            variacoes['Variação_Anual'].append(None)
            variacoes['Variação_7_Dias'].append(None)
            variacoes['Variação_45_Dias'].append(None)
            variacoes['Variação_90_Dias'].append(None)

    df_variacoes = pd.DataFrame(variacoes)

    # =========================
    # 4) Gerar PDF com scatter plots (mesma "qualidade gráfica")
    # =========================
    # Copiamos a mesma lógica do seu script
    buffer = io.BytesIO()
    with PdfPages(buffer) as pdf:
        classes_ativos = ['Moeda', 'Bolsa', 'Commodity']
        periodos_graficos = {
            '7 Dias': 'Variação_7_Dias',
            '45 Dias': 'Variação_45_Dias',
            '90 Dias': 'Variação_90_Dias',
            'Anual': 'Variação_Anual'
        }

        for classe in classes_ativos:
            # Ordenar por "Variação_Anual" (ascending=True, igual ao seu código)
            df_classe = df_variacoes[df_variacoes['Classe'] == classe].copy()
            df_classe = df_classe.sort_values(by='Variação_Anual', ascending=True)

            for titulo, coluna in periodos_graficos.items():
                fig, axs = plt.subplots(figsize=(11, 8))
                fig.suptitle(f'{classe} - Variação ({titulo}) - Ordenado pelo Retorno Anual', fontsize=16)

                # Monta o scatter
                # Observação: 'df_classe[coluna]' pode ter Nones, então convertemos para float e "dropna"
                dados_y = df_classe[coluna].astype(float)
                # range(len(df_classe)) é o eixo X, de 0 a n-1
                scatter = axs.scatter(
                    range(len(dados_y)),
                    dados_y,
                    c=dados_y,
                    cmap='RdYlGn',
                    s=150
                )

                axs.set_xlabel(f'{classe} - Ordenado pelo Retorno Anual', fontsize=12)
                axs.set_ylabel(f'Variação (%) - {titulo}', fontsize=12)
                axs.axhline(y=0, color='black', linestyle='--', linewidth=0.5)

                # Anota cada ponto com o "Nome_Amigavel"
                nomes_serie = df_classe['Nome_Amigavel'].tolist()
                for i, (valor_y, nome_txt) in enumerate(zip(dados_y, nomes_serie)):
                    if pd.notnull(valor_y):
                        axs.annotate(
                            nome_txt,
                            (i, valor_y),
                            textcoords="offset points",
                            xytext=(0, 10),
                            ha='center',
                            fontsize=8
                        )

                # Adiciona a barra de cores
                fig.colorbar(scatter, ax=axs, label='Variação (%)')

                # Remove os ticks do eixo X (pois estamos só enumerando)
                plt.xticks([])
                # Ajusta layout
                plt.tight_layout(rect=[0, 0.03, 1, 0.95])

                # Salva no PDF
                pdf.savefig(fig)
                plt.close(fig)

    buffer.seek(0)
    # Retorna o PDF como anexo
    return send_file(buffer, as_attachment=True, download_name="Variação_Dispersão.pdf")

if __name__ == "__main__":
    app.run(debug=True)
