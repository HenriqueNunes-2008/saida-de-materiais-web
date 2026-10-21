// Atualiza a prévia de conversão da embalagem para a unidade de estoque.
document.querySelectorAll('[data-conversion-form]').forEach((form) => {
  const purchase = form.querySelector('[data-purchase-unit]');
  const stock = form.querySelector('[data-stock-unit]');
  const box = form.querySelector('[data-box-fields]');
  const factor = form.querySelector('[data-units-per-package]');
  const received = form.querySelector('[data-received]');
  const price = form.querySelector('[data-price]');
  const preview = form.querySelector('[data-preview]');
  const money = (v, digits=2) => new Intl.NumberFormat('pt-BR', {style:'currency', currency:'BRL', minimumFractionDigits:digits, maximumFractionDigits:digits}).format(v);
  function refresh() {
    const isBox = purchase.value === 'CX';
    box.hidden = !isBox;
    factor.required = isBox;
    if (stock) {
      if (isBox) stock.value = 'UN';
      else stock.value = purchase.value;
      stock.querySelectorAll('option').forEach(option => { option.disabled = isBox ? option.value !== 'UN' : option.value !== purchase.value; });
    }
    const qty = received ? Number(received.value) : 0;
    const units = isBox ? Number(factor.value) : 1;
    const value = price ? Number(price.value.trim().replace(',', '.')) : 0;
    if (received && price && qty > 0 && Number.isInteger(qty) && units > 0 && Number.isInteger(units) && price.value.trim() !== '' && Number.isFinite(value) && value >= 0) {
      preview.textContent = `Entrada: ${(qty * units).toLocaleString('pt-BR')} ${stock ? stock.value : form.dataset.fixedStockUnit} | Preço por unidade: ${money(value / units, 4)} | Valor total: ${money(qty * value)}`;
    } else if (preview) preview.textContent = 'Informe quantidade, conversão e preço para visualizar os cálculos.';
  }
  [purchase, received, price, factor].filter(Boolean).forEach(el => el.addEventListener('input', refresh));
  refresh();
});
