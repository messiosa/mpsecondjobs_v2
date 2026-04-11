document.addEventListener('DOMContentLoaded', function() {
    function setupScrollArrows() {
        var wrapper = document.querySelector('.table-wrapper');
        var leftBtn = document.getElementById('scroll-left');
        var rightBtn = document.getElementById('scroll-right');
        var scrollable = wrapper ? wrapper.querySelector('.dash-spreadsheet-container') : null;

        if (!wrapper || !leftBtn || !rightBtn || !scrollable) {
            setTimeout(setupScrollArrows, 500);
            return;
        }

        function updateArrows() {
            var sl = scrollable.scrollLeft;
            var maxScroll = scrollable.scrollWidth - scrollable.clientWidth;
            leftBtn.classList.toggle('hidden', sl <= 5);
            rightBtn.classList.toggle('hidden', sl >= maxScroll - 5);
        }

        leftBtn.addEventListener('click', function() {
            scrollable.scrollBy({ left: -200, behavior: 'smooth' });
        });

        rightBtn.addEventListener('click', function() {
            scrollable.scrollBy({ left: 200, behavior: 'smooth' });
        });

        scrollable.addEventListener('scroll', updateArrows);
        window.addEventListener('resize', updateArrows);
        updateArrows();
    }

    setTimeout(setupScrollArrows, 1000);
});
