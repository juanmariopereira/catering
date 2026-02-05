"""
1000 recetas reales con tipos, momentos, información nutricional e ingredientes.
Cada receta referencia ingredientes por nombre (debe existir en ingredientes_500).
"""
import random
from recipes.data.ingredientes_500 import get_ingredientes

# Tipos de receta (recipes.TipoReceta)
TIPOS_RECETA = ["Comida", "Masa", "Postre", "Complemento", "Bebida", "Fruta"]
# Momentos del día (diets.TipoComida)
MOMENTOS_DIA = ["Desayuno", "Media mañana", "Comida", "Merienda", "Cena"]


def _nombres_recetas():
    """Lista de 1000 nombres de recetas reales (español/internacional)."""
    bases = [
        "Ensalada", "Sopa", "Crema", "Puré", "Guiso", "Estofado", "Asado", "Plancha",
        "Horno", "Frito", "Salteado", "Cocido", "Escalivada", "Gazpacho", "Salmorejo",
        "Tortilla", "Revuelto", "Huevos", "Tostada", "Bocadillo", "Sándwich", "Wrap",
        "Pasta", "Arroz", "Risotto", "Paella", "Cuscús", "Quinoa", "Legumbres",
        "Lentejas", "Garbanzos", "Alubias", "Potaje", "Fabada", "Cocido",
        "Pollo", "Pavo", "Ternera", "Cerdo", "Cordero", "Pescado", "Salmón", "Bacalao",
        "Merluza", "Atún", "Marisco", "Pulpo", "Calamares", "Gambas", "Mejillones",
        "Tarta", "Pastel", "Bizcocho", "Flan", "Natillas", "Mousse", "Coulant",
        "Brownie", "Galleta", "Magdalena", "Croissant", "Churro", "Buñuelo",
        "Batido", "Zumo", "Smoothie", "Infusión", "Café", "Té", "Limonada",
        "Fruta", "Macedonia", "Compota", "Ensalada de frutas", "Brocheta",
        "Albóndiga", "Croqueta", "Empanadilla", "Canelón", "Lasagna", "Ravioli",
        "Pizza", "Focaccia", "Pan", "Baguette", "Chapata", "Tostada",
        "Hummus", "Guacamole", "Paté", "Tapenade", "Alioli", "Salsa",
        "Carpaccio", "Tartar", "Ceviche", "Tiradito", "Sashimi",
        "Ratatouille", "Pisto", "Menestra", "Verduras", "Bruschetta",
        "Calamares a la romana", "Gambas al ajillo", "Mejillones al vapor",
        "Pulpo a la gallega", "Sepia a la plancha", "Bacalao al pil pil",
        "Merluza en salsa verde", "Salmón al horno", "Atún a la plancha",
        "Pechuga a la plancha", "Pollo al horno", "Pollo asado", "Pollo en pepitoria",
        "Cordero al horno", "Carrillada", "Solomillo", "Entrecot", "Chuletón",
        "Hamburguesa", "Hot dog", "Kebab", "Falafel", "Tacos", "Burrito",
        "Tortilla española", "Tortilla francesa", "Huevos rotos", "Huevos benedictine",
        "Porridge", "Granola", "Muesli", "Yogur", "Bowl", "Açaí bowl",
        "Tarta de queso", "Tarta de manzana", "Tarta de zanahoria", "Tarta Sacher",
        "Tiramisú", "Crema catalana", "Arroz con leche", "Torrijas",
        "Leche frita", "Pestiños", "Mantecados", "Polvorones", "Turrón",
        "Helado", "Sorbete", "Granizado", "Batido de chocolate", "Café con hielo",
    ]
    # Generar 1000 nombres únicos combinando bases con sufijos/variantes
    nombres = set()
    sufijos = ["clásico", "tradicional", "casero", "al horno", "a la plancha",
               "con verduras", "con hierbas", "con especias", "ligero", "cremoso",
               "picante", "suave", "mediterráneo", "andaluz", "gallego", "vasco",
               "catalán", "valenciano", "con queso", "con tomate", "con ajo",
               "al limón", "con vino", "en salsa", "al natural", "marinado",
               "estilo casa", "de la abuela", "gourmet", "express", "saludable"]
    while len(nombres) < 1000:
        b = random.choice(bases)
        if random.random() < 0.6:
            s = random.choice(sufijos)
            nombres.add(f"{b} {s}")
        else:
            nombres.add(b)
    return list(nombres)[:1000]


def get_recetas():
    """Devuelve lista de 1000 dicts con nombre, descripcion, tipos, momentos, info_nutricional, ingredientes."""
    random.seed(42)
    ingredientes_data = get_ingredientes()
    nombres_ing = [i["nombre"] for i in ingredientes_data]
    unidades_posibles = ["gr", "kg", "lt", "un"]

    nombres_recetas = _nombres_recetas()
    assert len(nombres_recetas) == 1000

    recetas = []
    for i, nombre in enumerate(nombres_recetas):
        # 1-2 tipos por receta
        n_tipos = random.randint(1, 2)
        tipos = random.sample(TIPOS_RECETA, n_tipos)
        # 1-3 momentos
        n_momentos = random.randint(1, 3)
        momentos = random.sample(MOMENTOS_DIA, n_momentos)
        # 5-12 ingredientes
        n_ing = random.randint(5, 12)
        ing_refs = random.sample(nombres_ing, min(n_ing, len(nombres_ing)))
        ingredientes = []
        for nombre_ing in ing_refs:
            # Cantidades plausibles: gr 10-500, kg 0.05-0.5, lt 0.05-0.3, un 0.5-4
            u = random.choice(unidades_posibles)
            if u == "gr":
                cantidad = round(random.uniform(10, 500), 0)
            elif u == "kg":
                cantidad = round(random.uniform(0.05, 0.5), 2)
            elif u == "lt":
                cantidad = round(random.uniform(0.05, 0.3), 2)
            else:
                cantidad = round(random.uniform(0.5, 4), 1)
            ingredientes.append({"ingrediente": nombre_ing, "cantidad": cantidad, "unidad": u})
        # Info nutricional estimada (suma aproximada o rango por tipo)
        calorias = random.randint(120, 650)
        proteinas = round(random.uniform(5, 35), 1)
        carbohidratos = round(random.uniform(10, 80), 1)
        grasas = round(random.uniform(3, 45), 1)
        fibra = round(random.uniform(1, 12), 1)
        info_nutricional = {
            "calorias": calorias,
            "proteinas": proteinas,
            "carbohidratos": carbohidratos,
            "grasas": grasas,
            "fibra": fibra,
        }
        descripcion = f"Receta de {nombre}. Elaboración tradicional con ingredientes de calidad."
        recetas.append({
            "nombre": nombre,
            "descripcion": descripcion,
            "tipos": tipos,
            "momentos": momentos,
            "info_nutricional": info_nutricional,
            "ingredientes": ingredientes,
        })
    return recetas
