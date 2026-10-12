"""Glossário fixo inglês → pt-BR para os campos de vocabulário fechado do dataset.

Nomes e descrições de produto não estão aqui: vêm da memória de tradução (`traducao.py`). Este glossário é a
fonte da verdade para cor, categoria, tipo e gênero, e também vai no prompt de quem traduz os nomes, para que
o mesmo termo saia igual no nome, no facet e na categoria.
"""

# color.original_name → nome da cor em pt-BR (minúsculo, como aparece no fim do nome do produto)
CORES: dict[str, str] = {
    "": "",
    "beige": "bege",
    "beige-black": "bege e preto",
    "beige-red": "bege e vermelho",
    "beige-white": "bege e branco",
    "black": "preto",
    "black-beige": "preto e bege",
    "black-blue": "preto e azul",
    "black-cream": "preto e creme",
    "black-grey": "preto e cinza",
    "black-red": "preto e vermelho",
    "black-rose": "preto e rosê",
    "black-white": "preto e branco",
    "black/gold": "preto e dourado",
    "black/white": "preto e branco",
    "blue": "azul",
    "blue-grey": "azul e cinza",
    "blue-red": "azul e vermelho",
    "blue-white": "azul e branco",
    "bordeaux": "bordô",
    "bronze": "bronze",
    "brown": "marrom",
    "brown-grey": "marrom e cinza",
    "chalk": "off-white",
    "chili": "vermelho-pimenta",
    "coral": "coral",
    "cream": "creme",
    "cream-black": "creme e preto",
    "cream-blue": "creme e azul",
    "dark blue": "azul-escuro",
    "dark brown": "marrom-escuro",
    "dark green": "verde-escuro",
    "dark grey": "cinza-escuro",
    "dark red": "vermelho-escuro",
    "fuschia": "fúcsia",
    "gold": "dourado",
    "green": "verde",
    "green-black": "verde e preto",
    "green-grey": "verde e cinza",
    "green-white": "verde e branco",
    "grey": "cinza",
    "grey-blue": "cinza e azul",
    "grey-white": "cinza e branco",
    "ice blue": "azul-gelo",
    "kakhi": "cáqui",
    "light blue": "azul-claro",
    "light brown": "marrom-claro",
    "light green": "verde-claro",
    "light grey": "cinza-claro",
    "light red": "vermelho-claro",
    "light rose": "rosê-claro",
    "luggage": "caramelo",
    "mandarin": "tangerina",
    "military green": "verde-militar",
    "mint green": "verde-menta",
    "multi": "multicolorido",
    "mustard yellow": "amarelo-mostarda",
    "navy": "azul-marinho",
    "nude": "nude",
    "ocean blue": "azul-oceano",
    "oliv": "verde-oliva",
    "oliv green": "verde-oliva",
    "olive": "verde-oliva",
    "orange": "laranja",
    "petrol": "azul-petróleo",
    "pink": "rosa",
    "platin": "platinado",
    "purple": "roxo",
    "red": "vermelho",
    "red-white": "vermelho e branco",
    "rose": "rosê",
    "rose-blue": "rosê e azul",
    "rose-cream": "rosê e creme",
    "rose-white": "rosê e branco",
    "silver": "prata",
    "sludge": "cinza-amarronzado",
    "sun": "amarelo-sol",
    "suntan": "camel",
    "tabacco": "tabaco",
    "taupe": "taupe",
    "turquoise": "turquesa",
    "vanilla": "baunilha",
    "violet": "violeta",
    "walnut": "marrom-nogueira",
    "watermelon": "melancia",
    "whiet": "branco",
    "white": "branco",
    "white-beige": "branco e bege",
    "white-blue": "branco e azul",
    "yellow": "amarelo",
    "yellow mustard": "amarelo-mostarda",
    "yellow-blue": "amarelo e azul",
}

# color.filter_group (antes do ";") → grupo de cor do facet
GRUPOS_COR: dict[str, str] = {
    "beige": "bege",
    "black": "preto",
    "blue": "azul",
    "brown": "marrom",
    "gold": "dourado",
    "green": "verde",
    "grey": "cinza",
    "multicolor": "multicolorido",
    "oliv": "verde-oliva",
    "orange": "laranja",
    "petrol": "azul-petróleo",
    "pink": "rosa",
    "purple": "roxo",
    "red": "vermelho",
    "silver": "prata",
    "turquoise": "turquesa",
    "white": "branco",
    "yellow": "amarelo",
}

GENEROS: dict[str, str] = {"women": "feminino", "men": "masculino"}

# Um segmento de categoria pode mudar de sentido conforme o pai ("Clothing" em Acessórios são lenços e
# cachecóis), por isso a chave é o caminho inteiro, como em hierarchical_categories.
CATEGORIAS: dict[str, str] = {
    "Women": "Feminino",
    "Men": "Masculino",
    "Accessories": "Acessórios",
    "Women > Bags": "Bolsas",
    "Women > Bags > Clutches": "Clutches",
    "Women > Bags > Handbag": "Bolsas de mão",
    "Women > Bags > Shopper": "Bolsas shopper",
    "Women > Bags > Shoulder bags": "Bolsas de ombro",
    "Women > Bags > Wallets": "Carteiras",
    "Women > Clothing": "Roupas",
    "Women > Clothing > Blazer": "Blazers",
    "Women > Clothing > Dresses": "Vestidos",
    "Women > Clothing > Jackets": "Casacos e jaquetas",
    "Women > Clothing > Jeans": "Jeans",
    "Women > Clothing > Shirts": "Camisas",
    "Women > Clothing > Skirts": "Saias",
    "Women > Clothing > T-shirts": "Camisetas",
    "Women > Clothing > Tops": "Blusas e malhas",
    "Women > Clothing > Trouser": "Calças",
    "Women > Shoes": "Calçados",
    "Women > Shoes > Ankle boots": "Botas",
    "Women > Shoes > Ballerinas": "Sapatilhas",
    "Women > Shoes > Loafers": "Mocassins",
    "Women > Shoes > Pumps": "Scarpins",
    "Women > Shoes > Sandals": "Sandálias",
    "Women > Shoes > Sneakers": "Tênis",
    "Men > Clothing": "Roupas",
    "Men > Clothing > Blazer": "Blazers",
    "Men > Clothing > Jackets": "Casacos e jaquetas",
    "Men > Clothing > Jeans": "Jeans",
    "Men > Clothing > Shirts": "Camisas",
    "Men > Clothing > Suits": "Ternos",
    "Men > Clothing > T-shirts": "Camisetas",
    "Men > Clothing > Tops": "Blusas e malhas",
    "Men > Clothing > Trousers": "Calças",
    "Men > Shoes": "Calçados",
    "Men > Shoes > Lace-up shoes": "Sapatos de amarrar",
    "Men > Shoes > Loafers": "Mocassins",
    "Men > Shoes > Sneakers": "Tênis",
    "Accessories > Women": "Feminino",
    "Accessories > Women > Clothing": "Vestuário",
    "Accessories > Women > Looks": "Looks",
    "Accessories > Women > Sunglasses": "Óculos de sol",
    "Accessories > Men": "Masculino",
    "Accessories > Men > Clothing": "Vestuário",
}

# Termos de nome de produto, para o prompt de tradução e para as checagens automáticas
TERMOS_PRODUTO: dict[str, str] = {
    "Sneaker(s)": "Tênis",
    "Runner": "Tênis Runner",  # modelo casual da Philippe Model, não tênis de corrida
    "Slip-On / Slip on": "Tênis slip-on",
    "Lace up shoe(s)": "Sapato de amarrar",
    "Mokassins / Loafer": "Mocassim",
    "Espadrille": "Alpargata",
    "Flip Flops": "Chinelo",
    "Sandals / sandalen": "Sandália",
    "Pumps": "Scarpin",
    "Ballerina(s)": "Sapatilha",
    "Booties": "Bota cano curto",
    "Bag": "Bolsa",
    "Shoulder bag": "Bolsa de ombro",
    "Handbag": "Bolsa de mão",
    "Shopper": "Bolsa shopper",
    "Bucket bag": "Bolsa saco",
    "Backpack": "Mochila",
    "Clutch": "Clutch",
    "Wallet": "Carteira",
    "Purse": "Porta-moedas",
    "Credit card holder": "Porta-cartões",
    "Makeup bag": "Nécessaire",
    "T-Shirt": "Camiseta",
    "Long sleeve T-Shirt": "Camiseta manga longa",
    "Long T-Shirt": "Camiseta longa",
    "Polo": "Camisa polo",
    "Shirt": "Camisa",
    "Top": "Blusa",
    "Sweater": "Suéter",
    "Cardigan": "Cardigã",
    "Hoodie": "Moletom com capuz",
    "Blazer": "Blazer",
    "Suit": "Terno",
    "Dress": "Vestido",
    "Skirt": "Saia",
    "Jeans / Biker jeans": "Calça jeans / Calça jeans biker",
    "Chino": "Calça chino",
    "Pants / Trousers / hosen": "Calça",
    "Jogging pants": "Calça de moletom",
    "Leggins": "Legging",
    "Shorts": "Shorts",
    "Overall": "Macacão",
    "Jacket": "Jaqueta",
    "Casual jacket": "Jaqueta casual",
    "Leather jacket": "Jaqueta de couro",
    "Down jacket": "Jaqueta de plumas",
    "Coat": "Casaco",
    "Parka": "Parca",
    "Trenchcoat": "Trench coat",
    "Vest": "Colete",
    "Poncho": "Poncho",
    "Scarf": "Cachecol",
    "Foulard": "Lenço",
    "Snood": "Gola cachecol",
    "Socks": "Meias",
    "Belt": "Cinto",
    "Sunglasses": "Óculos de sol",
    "Hat": "Chapéu",
    "Ring": "Anel",
    "Bracelet": "Pulseira",
    "Necklace": "Colar",
    "Keychain": "Chaveiro",
    "Battery": "Carregador portátil",
    "Phone case": "Capinha de celular",
    "Fitness watch": "Relógio fitness",
    "small / medium / large / mini": "pequena / média / grande / mini",
}


def categoria_pt(caminho: str) -> str:
    """Traduz um caminho "Women > Shoes > Sneakers" para "Feminino > Calçados > Tênis"."""
    partes = caminho.split(" > ")
    return " > ".join(CATEGORIAS[" > ".join(partes[: i + 1])] for i in range(len(partes)))


def grupo_cor_pt(filter_group: str) -> tuple[str, str]:
    """Separa "blue;#0075BB" em ("azul", "#0075BB"); o segundo é o swatch (hex ou URL de imagem)."""
    nome, _, swatch = filter_group.partition(";")
    return GRUPOS_COR[nome], swatch


# --- Inglês (a loja em /en) -------------------------------------------------------------------------------
# O texto de origem já está em inglês; aqui só se corrige o que a origem traz errado: grafia de cor, plural de
# categoria, sobras de alemão (os dados de exemplo vêm de uma loja alemã) e aspas trocadas.

CORES_EN: dict[str, str] = {
    "oliv": "olive",
    "oliv green": "olive green",
    "whiet": "white",
    "kakhi": "khaki",
    "fuschia": "fuchsia",
    "tabacco": "tobacco",
    "platin": "platinum",
    "multi": "multicolor",
    "sun": "sun yellow",
    "yellow mustard": "mustard yellow",
}
GRUPOS_COR_EN: dict[str, str] = {"oliv": "olive"}
GENEROS_EN: dict[str, str] = {"women": "women", "men": "men"}
CATEGORIAS_EN: dict[str, str] = {"Trouser": "Trousers", "Handbag": "Handbags", "Blazer": "Blazers"}
# palavra inteira (sem distinguir maiúscula) em nome e descrição: sobras de alemão e grafia errada da origem
PALAVRAS_EN: dict[str, str] = {
    "hosen": "pants",
    "handtaschen": "handbag",
    "mokassins": "loafers",
    "sandalen": "sandals",
    "und": "and",
    "leder": "leather",
    "kakhi": "khaki",
    "platin": "platinum",
    "whiet": "white",
}


def cor_en(original: str) -> str:
    """ "black-white" → "black and white"; corrige a grafia da origem ("whiet" → "white")."""
    cor = CORES_EN.get(original, original)
    return " and ".join(p.strip() for p in cor.replace("/", "-").split("-") if p.strip())


def categoria_en(caminho: str) -> str:
    return " > ".join(CATEGORIAS_EN.get(p, p) for p in caminho.split(" > "))


def grupo_cor_en(filter_group: str) -> tuple[str, str]:
    nome, _, swatch = filter_group.partition(";")
    return GRUPOS_COR_EN.get(nome, nome), swatch
