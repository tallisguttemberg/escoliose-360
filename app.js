/**
 * ESCOLIOSE 360° — LÓGICA DE APLICAÇÃO
 * Wizard multi-etapas de triagem e calculadora de risco.
 */

'use strict';

/* =========================================
   ESTADO DA APLICAÇÃO
   ========================================= */
const state = {
  respostas: {
    ombros: null,
    escapulas: null,
    cintura: null,
    adams: null,
    sexo: null,
    idade: null,
    menarca: null,
    historico: null,
  },
};

/* =========================================
   FLUXO DO WIZARD (MAPEAMENTO DE ETAPAS)
   ========================================= */
// Cada objeto descreve uma tela:
// { id, chave, totalSteps, currentStep }
const FLOW = [
  { id: 'step-consent',    chave: null,        total: 8, current: 0 },
  { id: 'step-ombros',     chave: 'ombros',    total: 8, current: 1 },
  { id: 'step-escapulas',  chave: 'escapulas', total: 8, current: 2 },
  { id: 'step-cintura',    chave: 'cintura',   total: 8, current: 3 },
  { id: 'step-adams',      chave: 'adams',     total: 8, current: 4 },
  { id: 'step-sexo',       chave: 'sexo',      total: 8, current: 5 },
  { id: 'step-idade',      chave: 'idade',     total: 8, current: 6 },
  // step-menarca é condicional — aparece apenas para 'feminino'
  { id: 'step-menarca',    chave: 'menarca',   total: 8, current: 7, condicional: true },
  { id: 'step-historico',  chave: 'historico', total: 8, current: 7 },
  { id: 'step-resultados', chave: null,        total: 8, current: 8 },
];

let flowIndex = 0; // Índice no FLOW atual

/* =========================================
   REFERÊNCIAS DOM
   ========================================= */
const $progressContainer = document.getElementById('progress-container');
const $progressBar       = document.getElementById('progress-bar');
const $progressText      = document.getElementById('progress-text');
const $btnConsent        = document.getElementById('btn-consent');
const $btnRestart        = document.getElementById('btn-restart');
const $btnWhatsapp       = document.getElementById('btn-whatsapp');
const $resultBadge       = document.getElementById('result-badge-level');
const $resultTitle       = document.getElementById('result-title');
const $resultDesc        = document.getElementById('result-description');
const $resultList        = document.getElementById('recommendation-list');

/* =========================================
   NAVEGAÇÃO ENTRE ETAPAS
   ========================================= */

/**
 * Mostra a tela correspondente ao FLOW[idx].
 * @param {number} idx - Índice dentro de FLOW
 */
function showStep(idx) {
  // Ocultar todas as telas
  document.querySelectorAll('.step-pane').forEach(el => el.classList.remove('active'));

  const step = FLOW[idx];
  const pane = document.getElementById(step.id);
  if (pane) pane.classList.add('active');

  // Barra de progresso
  const isFirstOrLast = step.current === 0 || step.id === 'step-resultados';
  $progressContainer.style.display = isFirstOrLast ? 'none' : 'block';

  if (!isFirstOrLast) {
    const pct = (step.current / step.total) * 100;
    $progressBar.style.width = `${pct}%`;
    $progressText.textContent = `Passo ${step.current} de ${step.total}`;
  }

  // Rolar o topo do card para cima
  const card = document.getElementById('wizard-card');
  if (card) card.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

/**
 * Avança para a próxima tela, respeitando condicionais.
 */
function nextStep() {
  flowIndex++;

  // Pular menarca se o sexo for masculino
  while (
    flowIndex < FLOW.length &&
    FLOW[flowIndex].condicional &&
    FLOW[flowIndex].id === 'step-menarca' &&
    state.respostas.sexo !== 'feminino'
  ) {
    flowIndex++;
  }

  if (flowIndex >= FLOW.length) {
    flowIndex = FLOW.length - 1;
  }

  showStep(flowIndex);

  // Se chegou na tela de resultados, calcular e exibir
  if (FLOW[flowIndex].id === 'step-resultados') {
    calcularResultado();
  }
}

/* =========================================
   REGISTRO DE RESPOSTAS
   ========================================= */

/**
 * Vincula todos os botões .btn-option de uma tela para registrar a resposta.
 * @param {string} stepId - ID do elemento <section>
 * @param {string} chave  - Chave em state.respostas
 */
function bindOptions(stepId, chave) {
  const pane = document.getElementById(stepId);
  if (!pane) return;

  pane.querySelectorAll('.btn-option').forEach(btn => {
    btn.addEventListener('click', () => {
      // Remover seleção anterior
      pane.querySelectorAll('.btn-option').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');

      // Salvar resposta
      state.respostas[chave] = btn.dataset.value;

      // Pequeno delay visual antes de avançar
      setTimeout(nextStep, 300);
    });
  });
}

/* =========================================
   CÁLCULO DE RISCO
   ========================================= */

/**
 * Calcula o nível de risco de progressão com base nas respostas coletadas.
 * 
 * CRITÉRIOS:
 * - Pontuação máxima: 10 pontos
 * - Alto Risco: >= 6 pontos
 * - Médio Risco: 3–5 pontos
 * - Baixo Risco: 0–2 pontos
 */
function calcularPontuacao() {
  let score = 0;

  const r = state.respostas;

  // Sinais Visuais
  if (r.ombros    === 'sim') score += 1;
  if (r.escapulas === 'sim') score += 1;
  if (r.cintura   === 'sim') score += 1;
  if (r.adams     === 'sim') score += 3; // Teste de Adams é o sinal mais relevante

  // Sexo (maior risco em mulheres)
  if (r.sexo === 'feminino') score += 1;

  // Idade (fase crítica de crescimento)
  if (r.idade === 'menos_10') score += 1;
  if (r.idade === '10_12')    score += 2;
  if (r.idade === '13_15')    score += 1;

  // Menarca (imaturidade esquelética = maior risco)
  if (r.sexo === 'feminino' && r.menarca === 'nao') score += 1;

  // Histórico Familiar
  if (r.historico === 'sim') score += 1;

  return score;
}

function calcularResultado() {
  const score = calcularPontuacao();

  // Limpar classes anteriores
  $resultBadge.classList.remove('alto', 'medio', 'baixo', 'result-loading');

  const sinaisVisuais = [
    state.respostas.ombros,
    state.respostas.escapulas,
    state.respostas.cintura,
    state.respostas.adams,
  ].filter(v => v === 'sim').length;

  const temGiba = state.respostas.adams === 'sim';

  let nivel, titulo, descricao, recomendacoes, whatsappMsg;

  if (score >= 6) {
    // --- ALTO RISCO ---
    nivel = 'alto';
    titulo = 'Alto Risco de Progressão';
    descricao = `Combinação crítica identificada: ${
      temGiba ? 'gibosidade presente no Teste de Adams + ' : ''
    }múltiplos sinais físicos + fatores clínicos de risco. A avaliação especializada é **urgente** para confirmar o diagnóstico e iniciar o acompanhamento adequado.`;
    recomendacoes = [
      'Agende avaliação IMEDIATA com ortopedista ou fisioterapeuta especializado em escoliose.',
      'Solicite ao médico a realização de radiografia panorâmica da coluna (AP e perfil).',
      'Documente por foto a postura atual para acompanhar a evolução.',
      'Evite atividades de impacto intenso até a avaliação médica.',
    ];
    whatsappMsg = `🚨 *ALTO RISCO DE PROGRESSÃO*\n\nAnalisador de Escoliose - Qualis Fisioterapia e Saúde\n\n✅ Sinais visuais positivos: ${sinaisVisuais}/4\n✅ Teste de Adams: ${temGiba ? 'Giba presente' : 'Negativo'}\n✅ Histórico familiar: ${state.respostas.historico === 'sim' ? 'Sim' : 'Não'}\n\nGostaria de agendar uma avaliação urgente.`;

  } else if (score >= 3) {
    // --- MÉDIO RISCO ---
    nivel = 'medio';
    titulo = 'Risco Moderado — Atenção!';
    descricao = `Foram identificados alguns sinais de assimetria postural que merecem atenção. Embora não indiquem necessariamente um diagnóstico de escoliose, recomendam uma avaliação profissional para monitoramento adequado.`;
    recomendacoes = [
      'Consulte um fisioterapeuta ou ortopedista nos próximos 30 dias.',
      'Realize exame postural completo para avaliação detalhada.',
      'Fortaleça a musculatura do core e da coluna com exercícios orientados.',
      'Repita este rastreio em 3 meses para monitorar a evolução.',
    ];
    whatsappMsg = `⚠️ *RISCO MODERADO*\n\nAnalisador de Escoliose - Qualis Fisioterapia e Saúde\n\n✅ Sinais visuais positivos: ${sinaisVisuais}/4\n✅ Teste de Adams: ${temGiba ? 'Giba presente' : 'Negativo'}\n\nGostaria de agendar uma avaliação postural.`;

  } else {
    // --- BAIXO RISCO ---
    nivel = 'baixo';
    titulo = 'Baixo Risco — Resultado Tranquilizador';
    descricao = `Não foram identificados sinais significativos de assimetria postural ou fatores de risco relevantes para escoliose neste momento. Continue com os cuidados habituais de postura e atividade física.`;
    recomendacoes = [
      'Continue incentivando atividade física regular e postura adequada.',
      'Faça rastreios anuais, especialmente durante fases de crescimento.',
      'Em caso de dúvidas ou mudanças perceptíveis, consulte um profissional.',
      'Uma boa ergonomia na escola e em casa é sempre recomendada.',
    ];
    whatsappMsg = `✅ *BAIXO RISCO*\n\nAnalisador de Escoliose - Qualis Fisioterapia e Saúde\n\nNão foram identificados sinais significativos. Gostaria de saber mais sobre prevenção de escoliose.`;
  }

  // Atualizar UI com animação
  setTimeout(() => {
    $resultBadge.textContent = titulo;
    $resultBadge.classList.add(nivel);
    $resultTitle.textContent = titulo;
    $resultDesc.textContent = descricao;

    $resultList.innerHTML = recomendacoes
      .map(rec => `<li>${rec}</li>`)
      .join('');

    // Gerar link dinâmico do WhatsApp
    const phone = '558881212701'; // Número do especialista
    const encodedMsg = encodeURIComponent(whatsappMsg);
    $btnWhatsapp.href = `https://wa.me/${phone}?text=${encodedMsg}`;
  }, 400);
}

/* =========================================
   REINICIAR AVALIAÇÃO
   ========================================= */
function reiniciar() {
  // Limpar estado
  Object.keys(state.respostas).forEach(k => (state.respostas[k] = null));

  // Limpar seleções visuais
  document.querySelectorAll('.btn-option').forEach(b => b.classList.remove('selected'));

  // Voltar ao início
  flowIndex = 0;
  showStep(0);
}

/* =========================================
   INICIALIZAÇÃO
   ========================================= */
function init() {
  // Vincular botão de consentimento
  $btnConsent.addEventListener('click', nextStep);

  // Vincular botão de reinício
  $btnRestart.addEventListener('click', reiniciar);

  // Vincular todos os passos de opção
  bindOptions('step-ombros',    'ombros');
  bindOptions('step-escapulas', 'escapulas');
  bindOptions('step-cintura',   'cintura');
  bindOptions('step-adams',     'adams');
  bindOptions('step-sexo',      'sexo');
  bindOptions('step-idade',     'idade');
  bindOptions('step-menarca',   'menarca');
  bindOptions('step-historico', 'historico');

  // Mostrar a primeira tela
  showStep(0);
}

// Iniciar quando o DOM estiver pronto
document.addEventListener('DOMContentLoaded', init);
