"""Serializers do cadastro de fornecedores.

Um serializer só para leitura e escrita: o formulário da tela é o registro
inteiro (não há passo a passo nem campos que só o backend preenche), então
dividir em dois só duplicaria a lista de campos.

O que o serializer acrescenta ao `ModelSerializer` são as regras que a tela
não pode garantir sozinha: dígito verificador do documento, unicidade dele
com a mensagem certa (e não o texto genérico do banco) e normalização de
CEP/telefone para dígitos.
"""

from __future__ import annotations

from rest_framework import serializers

from .documentos import documento_valido, somente_digitos
from .models import Fornecedor


class FornecedorSerializer(serializers.ModelSerializer):
    # A coluna do banco guarda 14 dígitos, mas o que chega da tela vem com
    # máscara ("11.222.333/0001-81", 18 caracteres). Sem redeclarar o campo,
    # o `max_length` herdado do model reprovaria o payload **antes** de
    # `validate_cnpj` tirar a pontuação — e o erro apareceria como "no
    # máximo 14 caracteres", que não diz nada a quem digitou certo.
    cnpj = serializers.CharField(max_length=32, required=False, allow_blank=True)

    # Derivados, para a tabela não ter que remontá-los em JS (e para a
    # planilha do Cotador usar o mesmo texto que a tela).
    cnpj_formatado = serializers.CharField(read_only=True)
    cidade_uf = serializers.CharField(read_only=True)
    situacao_label = serializers.CharField(source="get_situacao_display", read_only=True)
    categoria_label = serializers.CharField(source="get_categoria_display", read_only=True)

    class Meta:
        model = Fornecedor
        fields = [
            "id",
            "nome",
            "fantasia",
            "tipo",
            "cnpj",
            "cnpj_formatado",
            "inscricao_estadual",
            "categoria",
            "categoria_label",
            "cep",
            "logradouro",
            "numero",
            "complemento",
            "bairro",
            "uf",
            "cidade",
            "cidade_uf",
            "responsavel",
            "email",
            "telefone",
            "celular",
            "condicao_pagamento",
            "prazo_entrega_dias",
            "dados_bancarios",
            "chave_pix",
            "observacoes",
            "situacao",
            "situacao_label",
            "criado_em",
            "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate_nome(self, nome: str) -> str:
        nome = (nome or "").strip()
        if not nome:
            raise serializers.ValidationError("A razão social é obrigatória.")
        return nome

    def validate_cnpj(self, cnpj: str) -> str:
        digitos = somente_digitos(cnpj)
        if not digitos:
            # Opcional (GEN-19, 10/11/2026): sem documento não há o que
            # conferir nem com quem colidir.
            return ""
        if not documento_valido(digitos):
            raise serializers.ValidationError(
                "CNPJ/CPF inválido — confira os dígitos verificadores."
            )

        existente = Fornecedor.objects.filter(cnpj=digitos)
        if self.instance:
            existente = existente.exclude(pk=self.instance.pk)
        if outro := existente.first():
            raise serializers.ValidationError(
                f'Já existe um fornecedor com este CNPJ/CPF: "{outro.nome}".'
            )
        return digitos

    def validate_cep(self, cep: str) -> str:
        return somente_digitos(cep)

    def validate(self, dados: dict) -> dict:
        """Tipo e documento têm que combinar: CPF em cadastro de pessoa
        jurídica é erro de digitação, não uma variação aceitável — e passa
        despercebido até a hora de emitir nota."""

        tipo = dados.get("tipo") or getattr(self.instance, "tipo", "pj")
        cnpj = dados.get("cnpj") or getattr(self.instance, "cnpj", "")

        if cnpj:
            if tipo == "pf" and len(cnpj) != 11:
                raise serializers.ValidationError(
                    {"cnpj": "Pessoa física exige CPF (11 dígitos)."}
                )
            if tipo in ("pj", "mei") and len(cnpj) != 14:
                raise serializers.ValidationError(
                    {"cnpj": "Pessoa jurídica e MEI exigem CNPJ (14 dígitos)."}
                )
        return dados


class FornecedorOpcaoSerializer(serializers.ModelSerializer):
    """A versão enxuta que o Cotador usa para montar o seletor de
    fornecedor de um item.

    Existe separada da completa porque o modal do Cotador carrega o cadastro
    inteiro de uma vez (não é paginado — o operador precisa achar o
    fornecedor sem sair da cotação), e mandar endereço, PIX e observações de
    cada um só engordaria a resposta.
    """

    cnpj_formatado = serializers.CharField(read_only=True)
    situacao_label = serializers.CharField(source="get_situacao_display", read_only=True)

    class Meta:
        model = Fornecedor
        fields = [
            "id",
            "nome",
            "fantasia",
            "cnpj",
            "cnpj_formatado",
            "categoria",
            "cidade",
            "uf",
            "situacao",
            "situacao_label",
            "condicao_pagamento",
            "prazo_entrega_dias",
        ]
