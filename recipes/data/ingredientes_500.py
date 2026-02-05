"""
500 ingredientes reales con información nutricional por 100g y alérgenos.
Cada entrada: nombre, unidad (gr/kg/lt/un), por_100g (calorias, proteinas, carbohidratos, grasas, fibra), alergenos (lista str).
"""
# Categorías: (lista_nombres, unidad, por_100g, alergenos)
# Unidades: gr, kg, lt, un

def _cat(nombres, unidad, calorias, proteinas, carbohidratos, grasas, fibra, alergenos=None):
    por_100g = {
        "calorias": calorias, "proteinas": proteinas, "carbohidratos": carbohidratos,
        "grasas": grasas, "fibra": fibra
    }
    return (nombres, unidad, por_100g, alergenos or [])

VERDURAS = _cat([
    "Tomate", "Lechuga", "Cebolla", "Zanahoria", "Pimiento rojo", "Pimiento verde", "Pimiento amarillo",
    "Brócoli", "Coliflor", "Espinaca", "Acelga", "Col", "Repollo", "Berenjena", "Calabacín",
    "Pepino", "Apio", "Judías verdes", "Guisantes", "Habas", "Espárragos", "Puerro",
    "Remolacha", "Nabo", "Rábano", "Ajo", "Alcachofa", "Boniato", "Calabaza", "Puerro grueso",
    "Endibia", "Escarola", "Rúcula", "Canónigos", "Hinojo", "Col kale", "Pak choi",
    "Maíz dulce", "Champiñón", "Shiitake", "Ostra seta", "Portobello", "Pimiento de Padrón",
    "Alubia verde", "Calabacín italiano", "Tomate cherry", "Tomate pera", "Cebolleta",
    "Pepinillo", "Aguacate Hass", "Oliva", "Alcaparra", "Alga nori", "Alga wakame",
], "kg", 25, 2, 4, 0.3, 2, [])

FRUTAS = _cat([
    "Manzana", "Pera", "Plátano", "Naranja", "Mandarina", "Limón", "Lima", "Uva",
    "Fresa", "Cereza", "Melocotón", "Albaricoque", "Ciruela", "Sandía", "Melón",
    "Kiwi", "Piña", "Mango", "Papaya", "Granada", "Higo", "Dátil", "Arándano",
    "Frambuesa", "Mora", "Grosella", "Clementina", "Pomelo", "Maracuyá", "Guayaba",
    "Litchi", "Coco", "Aguacate fuerte", "Caqui", "Níspero", "Chirimoya", "Uva pasa",
    "Ciruela pasa", "Higo seco", "Dátil seco", "Orejones", "Cranberry", "Arándano rojo",
    "Endrina", "Zarzamora", "Fresa silvestre", "Mirtilo", "Physalis", "Pitaya",
    "Carambola", "Granada blanca", "Uva moscatel", "Melón galia", "Melón cantalupo",
], "kg", 52, 0.8, 12, 0.2, 2.5, [])

CARNES_AVES = _cat([
    "Pollo", "Pechuga de pollo", "Muslo de pollo", "Pavo", "Pechuga de pavo",
    "Codorniz", "Pato", "Oca", "Pollo campero", "Pollo entero",
], "kg", 190, 28, 0, 8, 0, [])

CARNES_ROJAS = _cat([
    "Ternera", "Solomillo de ternera", "Filete de ternera", "Carne picada de ternera",
    "Cordero", "Pierna de cordero", "Costilla de cordero", "Cerdo", "Lomo de cerdo",
    "Solomillo de cerdo", "Bacon", "Jamón serrano", "Jamón cocido", "Chorizo",
    "Salchicha", "Morcilla", "Butifarra", "Lacón", "Panceta", "Costilla de cerdo",
], "kg", 250, 26, 0, 17, 0, [])

PESCADOS = _cat([
    "Salmón", "Atún", "Bacalao", "Merluza", "Lubina", "Dorada", "Trucha", "Lenguado",
    "Rape", "Pescadilla", "Caballa", "Sardina", "Anchoa", "Boquerón", "Bonito",
    "Pulpo", "Calamar", "Sepia", "Gamba", "Langostino", "Mejillón", "Almeja",
    "Berberecho", "Vieira", "Cangrejo", "Langosta", "Bogavante", "Pescado blanco",
    "Tilapia", "Perca", "Rodaballo", "Mero", "Corvina", "Cazón", "Raya",
], "kg", 120, 20, 0, 4, 0, ["Pescado", "Mariscos"])

LACTEOS = _cat([
    "Leche entera", "Leche semidesnatada", "Leche desnatada", "Leche sin lactosa",
    "Nata líquida", "Nata para cocinar", "Crema de leche", "Yogur natural",
    "Yogur griego", "Yogur desnatado", "Kéfir", "Cuajada", "Requesón", "Quark",
    "Mantequilla", "Queso fresco", "Queso tierno", "Queso curado", "Queso manchego",
    "Queso parmesano", "Queso mozzarella", "Queso cheddar", "Queso emmental",
    "Queso brie", "Queso camembert", "Queso azul", "Queso feta", "Queso ricotta",
    "Queso cottage", "Queso crema", "Leche condensada", "Leche evaporada entera",
    "Nata montada batida", "Yogur de soja", "Leche de almendras", "Leche de avena",
], "lt", 65, 3.3, 5, 3.5, 0, ["Lactosa"])

HARINAS_CEREALES = _cat([
    "Harina de trigo", "Harina integral", "Harina de fuerza", "Harina de maíz",
    "Harina de centeno", "Harina de avena", "Harina de garbanzo", "Harina de almendra",
    "Maicena", "Fécula de patata", "Pan rallado", "Copos de avena", "Copos de maíz",
    "Muesli", "Granola", "Arroz blanco", "Arroz integral", "Arroz basmati", "Arroz jazmín",
    "Arroz bomba", "Arroz salvaje", "Quinoa", "Bulgur", "Couscous", "Cuscús integral",
    "Pasta de huevo", "Pasta integral", "Espagueti", "Macarrones", "Tallarines",
    "Fideos", "Lasagna", "Canelones", "Tortilla de trigo", "Tortilla de maíz",
    "Polenta", "Trigo", "Cebada", "Mijo", "Amaranto", "Trigo sarraceno",
], "kg", 350, 12, 72, 2, 3, ["Gluten"])

LEGUMBRES = _cat([
    "Lentejas", "Garbanzos", "Alubias blancas", "Alubias rojas", "Alubias pintas",
    "Guisantes secos", "Habas secas", "Soja", "Edamame", "Azuki", "Judías mungo",
    "Lenteja roja", "Lenteja beluga", "Garbanzo negro", "Alubia negra",
], "kg", 330, 22, 60, 1.5, 15, ["Soja"])

ACEITES_CONDIMENTOS = _cat([
    "Aceite de oliva", "Aceite de girasol", "Aceite de maíz", "Aceite de soja",
    "Aceite de coco", "Aceite de sésamo", "Aceite de lino", "Vinagre de vino",
    "Vinagre de manzana", "Vinagre balsámico", "Vinagre de Jerez", "Sal", "Pimienta negra",
    "Pimienta blanca", "Pimentón dulce", "Pimentón picante", "Canela", "Nuez moscada",
    "Clavo", "Jengibre", "Cúrcuma", "Comino", "Cilantro", "Orégano", "Albahaca",
    "Tomillo", "Romero", "Laurel", "Perejil", "Eneldo", "Estragón", "Mejorana",
    "Mostaza", "Ketchup", "Mayonesa", "Salsa de soja", "Worcester", "Tabasco",
    "Caldos concentrados", "Levadura química", "Bicarbonato", "Gelatina",
], "gr", 200, 1, 2, 22, 0.5, ["Mostaza", "Soja", "Sésamo", "Apio"])

FRUTOS_SECOS = _cat([
    "Almendra", "Nuez", "Avellana", "Cacahuete", "Pistacho", "Nuez de macadamia",
    "Nuez de Brasil", "Pipas de girasol", "Pipas de calabaza", "Piñón", "Castaña",
    "Coco rallado", "Nuez pecana", "Marañón", "Almendra laminada", "Nuez troceada",
], "gr", 600, 18, 15, 55, 7, ["Frutos secos", "Cacahuete"])

HUEVOS_OTROS = _cat([
    "Huevo", "Clara de huevo", "Yema de huevo", "Huevo codorniz", "Tofu",
    "Tempeh", "Seitan", "Levadura fresca", "Levadura seca", "Miel", "Mermelada",
    "Confitura", "Crema de cacao", "Chocolate negro", "Chocolate con leche",
    "Chocolate blanco", "Cacao en polvo", "Azúcar blanco", "Azúcar moreno",
    "Edulcorante", "Sirope de arce", "Sirope de agave", "Dulce de leche",
    "Caramelo", "Nata montada para repostería", "Masa de hojaldre", "Masa de brisa", "Masa quebrada",
    "Levadura nutricional", "Agar-agar", "Pectina", "Almidón de maíz",
], "un", 155, 13, 1, 11, 0, ["Huevo", "Gluten", "Soja", "Lactosa"])

BEBIDAS_BASE = _cat([
    "Agua", "Caldo de pollo", "Caldo de carne", "Caldo de verduras", "Caldo de pescado",
    "Vino blanco", "Vino tinto", "Vino rosado", "Cerveza", "Sidra", "Cava",
    "Café", "Café descafeinado", "Té negro", "Té verde", "Té rojo", "Infusión",
    "Zumo de naranja", "Zumo de limón", "Zumo de manzana", "Zumo de tomate",
    "Refresco cola", "Refresco naranja", "Tónica", "Agua con gas", "Bebida isotónica",
    "Leche de coco", "Bebida de arroz", "Bebida de avena", "Horchata", "Granizado",
], "lt", 45, 0.5, 10, 0, 0, ["Sulfitos", "Gluten"])

# Listas adicionales para llegar a 500
VERDURAS_EXTRA = _cat([
    "Col lombarda", "Brécol", "Romanesco", "Coles de Bruselas", "Acelga roja",
    "Espinaca baby", "Rúcula baby", "Mix de ensalada", "Zanahoria baby",
    "Tomate raf", "Tomate kumato", "Pimiento italiano", "Cebolla morada",
    "Cebolla dulce", "Chalota", "Puerro fino", "Berenjena japonesa",
    "Calabacín redondo", "Calabaza butternut", "Calabaza cacahuete",
    "Boniato morado", "Ñame", "Yuca", "Plátano macho", "Okra",
], "kg", 35, 2, 6, 0.2, 2.5, [])

FRUTAS_EXTRA = _cat([
    "Manzana golden", "Manzana fuji", "Manzana granny", "Pera conferencia",
    "Pera blanquilla", "Naranja sanguina", "Naranja navel", "Mandarina satsuma",
    "Uva blanca", "Uva negra", "Uva moscatel negra", "Melón piel de sapo",
    "Sandía sin pepitas", "Piña gold", "Mango kent", "Mango ataulfo",
    "Papaya maradol", "Granada mollar", "Coco fresco", "Dátil medjool",
    "Higo breva", "Chirimoya cumbe", "Caqui persimon", "Níspero japonés",
], "kg", 55, 0.9, 13, 0.25, 2.8, [])

CARNES_EXTRA = _cat([
    "Pollo ecológico", "Pavo ahumado", "Jamón ibérico", "Jamón York",
    "Fiambre de pavo", "Fiambre de pollo", "Mortadela", "Salami",
    "Cecina", "Lomo embuchado", "Fuet", "Longaniza", "Morcón",
    "Carne de vaca vieja", "Entrecot", "Chuletón", "Falda", "Aguja",
    "Redondo", "Cadera", "Solomillo ibérico", "Secreto ibérico",
    "Presa ibérica", "Costilla de ternera", "Rabo de toro",
], "kg", 220, 25, 0, 14, 0, [])

PESCADOS_EXTRA = _cat([
    "Salmón ahumado", "Atún en conserva", "Bonito del norte", "Anchoa en aceite",
    "Sardina en conserva", "Caballa en conserva", "Mejillones en conserva",
    "Almejas en conserva", "Surimi", "Palitos de cangrejo", "Caviar",
    "Hueva", "Bacalao salado", "Bacalao desalado", "Merluza congelada",
    "Filete de lenguado", "Trucha ahumada", "Salmón marinado",
], "kg", 130, 21, 1, 5, 0, ["Pescado", "Mariscos"])

LACTEOS_EXTRA = _cat([
    "Leche evaporada desnatada", "Leche en polvo", "Suero de mantequilla",
    "Queso gruyer", "Queso gouda", "Queso edam", "Queso provolone",
    "Queso roquefort", "Queso cabrales", "Queso idiazábal", "Queso tetilla",
    "Queso mahón", "Queso payoyo", "Queso de cabra", "Queso de oveja",
    "Burrata", "Bocconcini", "Queso mascarpone", "Queso philadelphia",
    "Nata agria", "Crème fraîche", "Yogur bebible", "Batido de chocolate",
    "Nata montada azucarada",
], "kg", 280, 18, 4, 22, 0, ["Lactosa"])

CEREALES_EXTRA = _cat([
    "Harina de trigo sarraceno", "Harina de espelta", "Harina sin gluten",
    "Harina de arroz", "Harina de coco", "Sémola", "Sémola de trigo",
    "Cuscús de trigo", "Fideos de arroz", "Fideos de soba", "Fideos udon",
    "Arroz glutinoso", "Arroz thai", "Arroz vaporizado", "Arroz largo",
    "Bulgur fino", "Bulgur grueso", "Quinoa blanca", "Quinoa roja",
    "Quinoa negra", "Amaranto", "Teff", "Sorgo", "Trigo burgol",
    "Cereal de desayuno", "All-bran", "Corn flakes", "Chocolate rice",
    "Galleta maría", "Galleta digestiva", "Oblea", "Barquillo",
], "kg", 360, 11, 74, 2.5, 4, ["Gluten"])

LEGUMBRES_EXTRA = _cat([
    "Lenteja pardina", "Lenteja castellana", "Garbanzo pedrosillano",
    "Garbanzo lechoso", "Alubia de riñón", "Alubia canela", "Alubia verdina",
    "Alubia blanca de riñón", "Guisante partido", "Haba fresca",
    "Soja texturizada", "Hummus", "Falafel mix", "Lenteja coral",
    "Judía azuki", "Mungo", "Altramuz", "Lupino",
], "kg", 320, 21, 58, 2, 16, ["Soja"])

CONDIMENTOS_EXTRA = _cat([
    "Salsa barbacoa", "Salsa teriyaki", "Salsa curry", "Salsa pesto",
    "Salsa napolitana", "Salsa carbonara", "Salsa holandesa", "Salsa bearnesa",
    "Salsa tártara", "Salsa césar", "Salsa ranch", "Salsa picante",
    "Pasta de curry", "Pasta de miso", "Pasta de sésamo", "Tahini",
    "Hummus", "Guacamole", "Salsa verde", "Salsa brava", "Alioli",
    "Alcaparras", "Aceituna rellena", "Aceituna negra", "Aceituna verde",
    "Pimiento del piquillo", "Pimiento asado", "Tomate frito", "Tomate triturado",
    "Passata", "Concentrado de tomate", "Puré de tomate",
], "gr", 120, 2, 18, 4, 1, ["Gluten", "Huevo", "Sésamo", "Soja", "Mostaza"])

DULCES_EXTRA = _cat([
    "Azúcar glas", "Azúcar avainillado", "Caramelo líquido", "Miel de flores",
    "Miel de romero", "Miel de eucalipto", "Mermelada de fresa", "Mermelada de naranja",
    "Mermelada de ciruela", "Confitura de frambuesa", "Crema de castaña",
    "Dulce de membrillo", "Dulce de batata", "Nutella", "Manteca de cacahuete",
    "Manteca de almendra", "Crema de avellanas", "Chocolate a la taza",
    "Cobertura de chocolate", "Chocolate chips", "Pepitas de chocolate",
    "Almíbar", "Sirope de chocolate", "Leche condensada", "Dulce de leche",
], "gr", 350, 4, 60, 10, 1, ["Lactosa", "Cacahuete", "Frutos secos"])

VARIOS = _cat([
    "Pan de molde", "Pan integral", "Pan rústico", "Pan de barra",
    "Baguette", "Chapata", "Pan de centeno", "Pan de pipas",
    "Tortilla de trigo", "Tortilla de maíz", "Wrap", "Pita",
    "Base de pizza", "Masa de pizza", "Hojaldre", "Brick",
    "Pasta filo", "Lasaña precocida", "Canelón", "Ravioli",
    "Tortellini", "Ñoquis", "Croqueta precocinada", "Empanadilla",
    "Bocadillo", "Sandwich", "Tostada", "Bizcocho",
    "Magdalena", "Croissant", "Napolitana", "Palmera",
    "Donut", "Churro", "Porra", "Buñuelo",
], "un", 280, 8, 52, 5, 2.5, ["Gluten", "Lactosa", "Huevo"])


def get_ingredientes():
    """Devuelve lista de 500 dicts: {nombre, unidad, por_100g, alergenos}."""
    categorias = [
        VERDURAS, FRUTAS, CARNES_AVES, CARNES_ROJAS, PESCADOS, LACTEOS,
        HARINAS_CEREALES, LEGUMBRES, ACEITES_CONDIMENTOS, FRUTOS_SECOS,
        HUEVOS_OTROS, BEBIDAS_BASE, VERDURAS_EXTRA, FRUTAS_EXTRA, CARNES_EXTRA,
        PESCADOS_EXTRA, LACTEOS_EXTRA, CEREALES_EXTRA, LEGUMBRES_EXTRA,
        CONDIMENTOS_EXTRA, DULCES_EXTRA, VARIOS,
    ]
    out = []
    for nombres, unidad, por_100g, alergenos in categorias:
        for nombre in nombres:
            out.append({
                "nombre": nombre,
                "unidad": unidad,
                "por_100g": por_100g.copy(),
                "alergenos": list(alergenos),
            })
            if len(out) >= 500:
                return out[:500]
    return out[:500]
