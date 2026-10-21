// Controla a busca acessível de materiais e valida a quantidade antes da saída.
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('material_search');
  const productId = document.getElementById('product_id');
  const wrapper = input?.closest('.material-autocomplete');
  const list = document.getElementById('material_suggestions');
  const quantity = document.getElementById('quantidade');
  const preview = document.getElementById('output_preview');
  const form = input?.closest('form');
  if (!input || !productId || !wrapper || !list || !preview) return;

  const brl = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });
  let timer, requestNumber = 0, activeIndex = -1, selected = null;
  const setOpen = open => {
    list.hidden = !open;
    input.setAttribute('aria-expanded', String(open));
  };
  const showMessage = (message, state = '') => {
    list.replaceChildren();
    const item = document.createElement('li');
    item.className = `material-suggestion-message ${state}`;
    item.textContent = message;
    item.setAttribute('role', 'status');
    list.append(item);
    activeIndex = -1;
    setOpen(true);
  };
  const updatePreview = () => {
    if (!selected) {
      preview.textContent = 'Selecione um produto para consultar saldo e preço.';
      return;
    }
    const qty = Number(String(quantity?.value || '').replace(',', '.'));
    const stock = Number(selected.stock);
    const price = selected.price === null ? null : Number(selected.price);
    preview.textContent = `Saldo: ${selected.stock} ${selected.unit} | Último preço: ${price === null ? 'não informado' : brl.format(price)}${qty > 0 && price !== null ? ` | Valor da saída: ${brl.format(qty * price)}` : ''}${qty > stock ? ' | SALDO INSUFICIENTE' : ''}`;
  };
  const choose = item => {
    selected = item;
    productId.value = String(item.id);
    input.value = `${item.code} — ${item.description}`;
    input.removeAttribute('aria-activedescendant');
    setOpen(false);
    updatePreview();
  };
  const render = items => {
    list.replaceChildren();
    activeIndex = -1;
    if (!items.length) return showMessage('Nenhum material encontrado');
    items.forEach((item, index) => {
      const option = document.createElement('li');
      option.id = `material-option-${index}`;
      option.className = 'material-suggestion';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', 'false');
      const title = document.createElement('span');
      title.className = 'material-suggestion-title';
      title.textContent = `${item.code} — ${item.description}`;
      const details = document.createElement('span');
      details.className = 'material-suggestion-details';
      details.textContent = `Unidade: ${item.unit} | Saldo: ${item.stock} ${item.unit}`;
      option.append(title, details);
      option.addEventListener('mousedown', event => event.preventDefault());
      option.addEventListener('click', () => choose(item));
      list.append(option);
    });
    setOpen(true);
  };
  const search = async term => {
    const current = ++requestNumber;
    if (term.length < 2) { setOpen(false); return; }
    showMessage('Buscando materiais…', 'loading');
    try {
      const response = await fetch(`${wrapper.dataset.searchUrl}?q=${encodeURIComponent(term)}`, {
        headers: { 'Accept': 'application/json' }, credentials: 'same-origin'
      });
      if (current !== requestNumber) return;
      if (!response.ok) throw new Error('Busca indisponível');
      const data = await response.json();
      if (current === requestNumber) render(data.items || []);
    } catch (_error) {
      if (current === requestNumber) showMessage('Erro ao buscar materiais. Tente novamente.', 'error');
    }
  };
  input.addEventListener('input', () => {
    requestNumber += 1;
    selected = null;
    productId.value = '';
    input.removeAttribute('aria-activedescendant');
    updatePreview();
    clearTimeout(timer);
    const term = input.value.trim();
    timer = setTimeout(() => search(term), 250);
  });
  input.addEventListener('keydown', event => {
    const options = [...list.querySelectorAll('[role="option"]')];
    if (event.key === 'ArrowDown' && options.length) {
      event.preventDefault(); activeIndex = (activeIndex + 1) % options.length;
    } else if (event.key === 'ArrowUp' && options.length) {
      event.preventDefault(); activeIndex = (activeIndex - 1 + options.length) % options.length;
    } else if (event.key === 'Enter' && activeIndex >= 0 && options[activeIndex]) {
      event.preventDefault(); options[activeIndex].click();
    } else if (event.key === 'Escape') {
      setOpen(false); input.removeAttribute('aria-activedescendant'); return;
    } else return;
    options.forEach((option, index) => {
      const active = index === activeIndex;
      option.classList.toggle('is-active', active);
      option.setAttribute('aria-selected', String(active));
    });
    input.setAttribute('aria-activedescendant', options[activeIndex].id);
  });
  document.addEventListener('click', event => {
    if (!wrapper.contains(event.target)) setOpen(false);
  });
  quantity?.addEventListener('input', updatePreview);
  form?.addEventListener('submit', event => {
    if (!selected || productId.value !== String(selected.id)) {
      event.preventDefault();
      input.setCustomValidity('Selecione um material da lista de sugestões.');
      input.reportValidity();
      input.focus();
    } else if (quantity && Number(String(quantity.value).replace(',', '.')) > Number(selected.stock)) {
      event.preventDefault();
      quantity.setCustomValidity('Saldo insuficiente para esta saída.');
      quantity.reportValidity();
      quantity.focus();
    }
  });
  input.addEventListener('input', () => input.setCustomValidity(''));
  quantity?.addEventListener('input', () => quantity.setCustomValidity(''));
  updatePreview();
});
