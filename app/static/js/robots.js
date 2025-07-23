// Funções para melhorar a experiência do dropdown em dispositivos móveis
document.addEventListener('DOMContentLoaded', function() {
    const contactTitleSelect = document.getElementById('contact_title');
    
    if (!contactTitleSelect) return;
    
    // Ajusta o tamanho do dropdown com base no dispositivo
    function adjustSelectSize() {
        const isMobile = window.innerWidth < 768;
        
        // Em dispositivos móveis, adicionamos classes específicas
        if (isMobile) {
            contactTitleSelect.classList.add('mobile-select');
        } else {
            contactTitleSelect.classList.remove('mobile-select');
        }
    }
    
    // Executa no carregamento
    adjustSelectSize();
    
    // Executa quando a janela é redimensionada
    window.addEventListener('resize', adjustSelectSize);
    
    // Melhora a experiência em dispositivos touch
    contactTitleSelect.addEventListener('touchstart', function() {
        this.classList.add('select-active');
    });
    
    // Limpa a classe após a seleção
    contactTitleSelect.addEventListener('change', function() {
        this.classList.remove('select-active');
    });
});
