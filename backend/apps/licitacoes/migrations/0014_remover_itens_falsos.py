"""Apaga os 3 itens que a Sentinela gravou sem proposta da Inside (defeito
corrigido em 09/11/2026: abrir no Compras.gov um item em que a empresa não
entrou criava o item). Lista conferida pela operação em 09/11/2026:

- Pregão 56/2026 (PM-DF), itens 1 (estabilizador) e 3 (aspirador cirúrgico);
- Pregão 59/2026 (Fazenda Rio Grande/PR), item 1 (laringoscópio).

Só apaga se o item **ainda** estiver sem preço, sem marca e sem posição, e
deixa uma linha no histórico da compra.
"""

from django.db import migrations

ALVOS = {
    "92667005000562026": ["1", "3"],
    "98998305000592026": ["1"],
}
MOTIVO = (
    "Item {n} removido: foi aberto no Compras.gov, mas a Inside não deu preço nele "
    "(gravado por engano pela Sentinela; correção de 09/11/2026)."
)


def apagar(apps, schema_editor):
    Item = apps.get_model("licitacoes", "ItemParticipado")
    Evento = apps.get_model("licitacoes", "EventoOportunidadeSalva")
    for codigo, numeros in ALVOS.items():
        itens = Item.objects.filter(
            oportunidade__link_plataforma__contains=f"compra={codigo}",
            numero_item__in=numeros,
            fonte="sentinela",
            marca="",
            classificacao__isnull=True,
            valor_proposta_inicial__isnull=True,
            valor_lance_final__isnull=True,
        )
        for item in itens:
            Evento.objects.create(
                oportunidade_id=item.oportunidade_id,
                tipo="correcao",
                descricao=MOTIVO.format(n=item.numero_item),
                autor_nome="Licita",
                dados={"item": item.numero_item, "descricao": item.descricao},
            )
            item.delete()


class Migration(migrations.Migration):
    dependencies = [("licitacoes", "0013_tipo_correcao")]
    operations = [migrations.RunPython(apagar, migrations.RunPython.noop)]
