"""
Testes unitários do BluaDiagnostics.

Roda com:  pytest tests/ -v

A gente focou os testes nas partes determinísticas do sistema (tools e
guardrails), que dá pra testar sem gastar chamada de API. Isso cobre o
bônus de "testes unitários para as tools" e serve de teste de regressão:
se alguém mexer numa regra de red flag e quebrar, o teste pega.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.clinical_tools import (
    agendar_teleconsulta,
    consultar_historico_paciente,
    obter_sinais_vitais_wearable,
    verificar_interacoes_medicamentosas,
)
from src.graph.guardrails import checar_escopo, checar_moderacao, checar_red_flag


# --------------------------------------------------------------------------
# Tools
# --------------------------------------------------------------------------
class TestTools:
    def test_historico_paciente_existente(self):
        r = consultar_historico_paciente("12345678901")
        assert r["encontrado"] is True
        assert r["nome"] == "Maria"
        assert r["idade"] == 34
        assert "hipertensão arterial" in r["comorbidades"]

    def test_historico_paciente_inexistente(self):
        r = consultar_historico_paciente("00000000000")
        assert r["encontrado"] is False

    def test_interacao_losartana_ibuprofeno(self):
        r = verificar_interacoes_medicamentosas(["losartana", "ibuprofeno"])
        assert r["severidade_geral"] == "moderada"
        assert len(r["interacoes_encontradas"]) == 1

    def test_interacao_sem_conflito(self):
        r = verificar_interacoes_medicamentosas(["paracetamol", "vitamina c"])
        assert r["severidade_geral"] == "nenhuma"
        assert r["interacoes_encontradas"] == []

    def test_agendar_teleconsulta_retorna_protocolo(self):
        r = agendar_teleconsulta("12345678901", "clinico_geral", "breve", "dor de cabeça")
        assert r["status"] == "confirmado"
        assert r["protocolo"].startswith("BLUA-")
        assert r["especialidade"] == "clinico_geral"

    def test_wearable_disponivel(self):
        r = obter_sinais_vitais_wearable("12345678901", "apple_health")
        assert r["disponivel"] is True
        assert "frequencia_cardiaca_media_bpm" in r

    def test_wearable_inexistente(self):
        r = obter_sinais_vitais_wearable("00000000000", "apple_health")
        assert r["disponivel"] is False


# --------------------------------------------------------------------------
# Guardrails
# --------------------------------------------------------------------------
class TestGuardrails:
    def test_red_flag_dor_no_peito(self):
        r = checar_red_flag("estou com uma dor forte no peito irradiando pro braço")
        assert r["detectado"] is True
        assert r["saude_mental"] is False

    def test_red_flag_avc(self):
        r = checar_red_flag("ela está sem força no braço e com a fala enrolada")
        assert r["detectado"] is True

    def test_red_flag_saude_mental(self):
        r = checar_red_flag("não quero mais viver, quero acabar com tudo")
        assert r["detectado"] is True
        assert r["saude_mental"] is True

    def test_sem_red_flag_em_sintoma_leve(self):
        r = checar_red_flag("estou com uma coriza leve e espirrando")
        assert r["detectado"] is False

    def test_escopo_pergunta_de_saude(self):
        r = checar_escopo("estou com febre e dor de garganta")
        assert r["no_escopo"] is True

    def test_escopo_fora_redacao(self):
        r = checar_escopo("me ajuda a fazer uma redação pro vestibular")
        assert r["no_escopo"] is False

    def test_escopo_fora_investimento(self):
        r = checar_escopo("qual o melhor investimento pra 2026")
        assert r["no_escopo"] is False

    def test_moderacao_aprova_normal(self):
        r = checar_moderacao("estou com dor de cabeça")
        assert r["aprovado"] is True


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
