// Ajusta os passos dos campos de quantidade conforme a unidade escolhida.
document.addEventListener('DOMContentLoaded', () => {
  const unit = document.getElementById('unit');
  const quantity = document.getElementById('quantity');
  if (!unit || !quantity) return;

  const limits = [
    document.getElementById('minimum_stock'),
    document.getElementById('reorder_point'),
    document.getElementById('maximum_stock'),
  ].filter(Boolean);

  // Apenas KG, M, MT e LT aceitam fracoes; as demais unidades usam inteiros.
  const updateSteps = () => {
    const fractional = ['KG', 'M', 'MT', 'LT'].includes(unit.value);
    quantity.step = fractional ? '0.001' : '1';
    quantity.min = fractional ? '0.001' : '1';
    limits.forEach((input) => { input.step = fractional ? '0.001' : '1'; });
  };

  unit.addEventListener('change', updateSteps);
  updateSteps();
});
