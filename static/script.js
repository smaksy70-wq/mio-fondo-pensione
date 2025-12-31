
const API_BASE = "/api";

// State
let funds = [];
let chartInstance = null;

// DOM Elements
const searchInp = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const fundList = document.getElementById('fundList');
const countBadge = document.getElementById('countBadge');
const detailPanel = document.getElementById('detailPanel');
const loadingIndicator = document.getElementById('loadingFunds');

// Init
document.addEventListener('DOMContentLoaded', async () => {
    loadingIndicator.classList.remove('hidden');

    // Mobile Back Button Logic
    const backBtn = document.getElementById('backBtn');
    if (backBtn) {
        backBtn.onclick = () => {
            document.querySelector('.list-container').classList.remove('hidden-mobile');
            detailPanel.classList.remove('visible-mobile');
            detailPanel.classList.add('hidden');
        };
    }

    try {
        const res = await fetch(`${API_BASE}/funds`);
        funds = await res.json();
    } catch (e) {
        console.error("Failed to load funds", e);
        loadingIndicator.innerText = "Errore nel caricamento dei fondi. Ricarica la pagina.";
        loadingIndicator.style.color = "#ef4444";
        loadingIndicator.classList.remove('hidden');
        return;
    } finally {
        if (funds.length > 0) loadingIndicator.classList.add('hidden');
    }
});

// Search
const handleSearch = () => {
    const term = searchInp.value.toLowerCase();

    // Hide list if empty input
    if (term.length === 0) {
        document.querySelector('.list-container').classList.remove('visible');
        return;
    }

    const filtered = funds.filter(f =>
        f.name.toLowerCase().includes(term) ||
        f.albo.includes(term)
    );

    renderList(filtered);

    // Show list if results exist
    if (filtered.length > 0) {
        document.querySelector('.list-container').classList.add('visible');
    } else {
        document.querySelector('.list-container').classList.remove('visible');
    }
};

// Explicit search only
searchInp.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
        handleSearch();
    }
});
searchBtn.addEventListener('click', handleSearch);

function renderList(items) {
    fundList.innerHTML = '';
    countBadge.innerText = items.length;

    items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'fund-item';
        li.innerHTML = `
            <span class="fund-name">${item.name}</span>
            <div class="fund-meta">Albo: ${item.albo} | Tipo: ${item.type}</div>
        `;
        li.onclick = () => selectFund(item, li);
        fundList.appendChild(li);
    });
}

async function selectFund(fund, el) {
    // Highlight
    document.querySelectorAll('.fund-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');

    // Mobile specific: hide list and show details
    document.querySelector('.list-container').classList.add('hidden-mobile');
    detailPanel.classList.add('visible-mobile');

    // Show Details
    detailPanel.classList.remove('hidden');
    document.getElementById('detailTitle').innerText = fund.name;
    document.getElementById('detailType').innerText = fund.type;
    document.getElementById('pdfLink').href = fund.link;
    document.getElementById('viewPdfLink').href = `${API_BASE}/proxy_pdf?url=${encodeURIComponent(fund.link)}`;

    // Reset Analysis
    const chartsContainer = document.getElementById('chartsContainer');
    const costError = document.getElementById('costError');
    const costLoading = document.getElementById('costLoading');

    chartsContainer.classList.add('hidden');
    chartsContainer.innerHTML = ''; // clear old charts
    costError.classList.add('hidden');
    costLoading.classList.remove('hidden');

    if (!fund.link) {
        costLoading.classList.add('hidden');
        costError.innerText = "Nessun link PDF disponibile per questo fondo.";
        costError.classList.remove('hidden');
        return;
    }

    // Fetch details
    try {
        // Fetch PDF analysis
        const encodedUrl = encodeURIComponent(fund.link);
        const encodedName = encodeURIComponent(fund.name);
        const encodedAlbo = encodeURIComponent(fund.albo);

        // Add Albo/Name to query for Excel lookup
        const res = await fetch(`${API_BASE}/analyze?url=${encodedUrl}&type=${fund.type}&albo=${encodedAlbo}&name=${encodedName}`);
        const data = await res.json();

        if (data.error) {
            throw new Error(data.error);
        }

        renderAnalysis(data);
    } catch (e) {
        costError.innerText = "Errore nell'estrazione dei dati: " + e.message;
        costError.classList.remove('hidden');
    } finally {
        costLoading.classList.add('hidden');
    }
}

function renderAnalysis(data) {
    const container = document.getElementById('chartsContainer');
    container.classList.remove('hidden');
    container.innerHTML = ''; // Clean


    // 1. Render PDF Page Image (Exact Copy from PDF)
    if (data.chart_image) {
        const card = document.createElement('div');
        card.className = 'chart-card';
        card.style.gridColumn = "1 / -1";

        const h4 = document.createElement('h4');
        h4.innerText = "Grafico ISC dal Documento Originale";
        card.appendChild(h4);

        const img = document.createElement('img');
        img.src = data.chart_image;
        img.style.width = "100%";
        img.style.borderRadius = "8px";
        img.style.border = "1px solid var(--border)";
        card.appendChild(img);

        container.appendChild(card);
    } else {
        const errDiv = document.createElement('div');
        errDiv.className = 'chart-card';
        errDiv.innerHTML = "<p>Impossibile estrarre il grafico dal PDF.</p>";
        container.appendChild(errDiv);
    }
}
