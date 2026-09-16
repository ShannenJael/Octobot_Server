$(function () {
    $('[data-strategy-toggle]').on('click', function () {
        const $button = $(this);
        const $panel = $('#' + $button.attr('aria-controls'));
        const isOpen = $button.attr('aria-expanded') === 'true';
        $button.attr('aria-expanded', String(!isOpen));
        $panel.prop('hidden', isOpen);
    });

    $('[data-focus-strategy]').on('click', function () {
        const index = Number($(this).attr('data-focus-strategy'));
        const $card = $('[data-strategy-card]').eq(index);
        const $toggle = $card.find('[data-strategy-toggle]');
        if ($toggle.attr('aria-expanded') !== 'true') {
            $toggle.trigger('click');
        }
        $('[data-strategy-card]').removeClass('strategy-card-focus');
        $card.addClass('strategy-card-focus');
        window.setTimeout(function () { $card.removeClass('strategy-card-focus'); }, 1800);
    });
});
