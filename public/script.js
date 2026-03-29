// Viewport height fix for mobile browsers
function setVh() {
    var vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', vh + 'px');
}
setVh();
window.addEventListener('resize', setVh);

// List of fun loading messages
var loadingMessages = [
    "Downloading: Bottling up the magic.",
    "Downloading: Wrapping your sparkles in stardust.",
    "Downloading: Charging up the glitter cannons.",
    "Downloading: Gently placing your sparkles in the cosmos.",
    "Downloading: Painting rainbows with your sparkles.",
    "Downloading: Shaking the snow globe of dreams.",
    "Downloading: Bedazzling the pixels.",
    "Downloading: Warming up the sparkle machine.",
    "Downloading: Collecting shooting stars.",
    "Downloading: Mixing colors for extra shimmer.",
    "Downloading: Glitter levels at maximum capacity.",
    "Downloading: Wrapping sparkles in a tiny gift box.",
    "Downloading: Adjusting the glow-in-the-dark setting.",
    "Downloading: Teaching rainbows how to dance.",
    "Downloading: Asking the sun for a little extra shine.",
    "Downloading: Translating sparkles into star language.",
    "Downloading: Powering up the joy reactor.",
    "Downloading: Consulting the kittens of wisdom.",
    "Downloading: Beaming your sparkles to a secret garden.",
    "Downloading: Fluffing the clouds for extra coziness."
];

function adjustPhotoContainer() {
    var footerHeight = document.querySelector('footer').offsetHeight;
    var viewportHeight = window.innerHeight;
    document.getElementById('photoContainer').style.height = (viewportHeight - footerHeight) + 'px';
}
window.addEventListener('resize', adjustPhotoContainer);

function updateContent(data) {
    document.getElementById('heartButton').classList.remove('liked');
    var photo = document.getElementById('photo');
    photo.style.opacity = 0;

    setTimeout(function() {
        photo.src = data.photoUrl;
        photo.onload = function() {
            photo.style.opacity = 1;
        };
        document.getElementById('quote').textContent = data.quote;
        document.getElementById('instagramLink').href = data.instagramLink;
        document.getElementById('instagramLink').textContent = data.instagramName;
    }, 500);
}

// Click photo to load new content
document.querySelector('#photoContainer').addEventListener('click', function() {
    fetch('/data')
        .then(function(response) { return response.json(); })
        .then(function(data) { updateContent(data); });
});

// Initial load
document.getElementById('photoContainer').style.display = 'none';
document.querySelector('.container').style.display = 'none';

fetch('/data')
    .then(function(response) { return response.json(); })
    .then(function(data) {
        updateContent(data);
        adjustPhotoContainer();
        setTimeout(function() {
            document.getElementById('loadingScreen').style.display = 'none';
            document.getElementById('photoContainer').style.display = 'block';
            document.querySelector('.container').style.display = 'block';
        }, 1000);
    });

// Rainbow loading text
document.addEventListener('DOMContentLoaded', function() {
    var loadingText = "\u2728 Loading virtual sparkles \u2728 please wait... \u2728";
    var rainbowColors = ['red', 'orange', 'green', 'blue', 'indigo', 'violet'];
    var words = loadingText.split(' ');
    var coloredText = '';
    words.forEach(function(word) {
        coloredText += '<span>';
        for (var i = 0; i < word.length; i++) {
            var color = rainbowColors[i % rainbowColors.length];
            coloredText += '<span style="color:' + color + ';">' + word[i] + '</span>';
        }
        coloredText += '</span>';
    });
    document.getElementById('loadingText').innerHTML = coloredText;

    var spans = document.querySelectorAll('#loadingText span');
    spans.forEach(function(span) {
        span.style.animation = 'pulse 1.5s infinite alternate';
    });
});

// Heart (like) button
var tooltip = document.createElement('div');
tooltip.id = 'tooltip';
document.body.appendChild(tooltip);

document.getElementById('heartButton').addEventListener('click', function(event) {
    tooltip.style.display = 'none';
    event.stopPropagation();

    var quote = document.getElementById('quote').textContent;

    fetch('/like', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quote: quote })
    })
    .then(function(response) { return response.json(); })
    .then(function(data) {
        if (data.result === 'success') {
            document.getElementById('heartButton').classList.add('liked');
        } else {
            console.error('Error:', data.error);
        }
    })
    .catch(function(error) { console.error('Fetch error:', error); });
});

// Download button
document.getElementById('downloadButton').addEventListener('click', function(event) {
    event.stopPropagation();

    var statusBox = document.getElementById('downloadStatusBox');
    var loadingMessage = document.getElementById('loadingMessage');
    var emojiAnimation = document.getElementById('emojiAnimation');

    statusBox.style.opacity = '1';
    statusBox.style.display = 'flex';
    loadingMessage.textContent = '\u2728 Preparing sparkles... \u2728';
    emojiAnimation.innerHTML = '';

    statusBox.style.bottom = '5px';
    statusBox.style.left = '10px';

    var index = 0;
    var messageInterval = setInterval(function() {
        loadingMessage.textContent = loadingMessages[index];
        index = (index + 1) % loadingMessages.length;
    }, 1000);

    var sparkles = ['\u2728', '\uD83D\uDCAB', '\uD83C\uDF1F', '\u2728', '\uD83D\uDCAB', '\uD83C\uDF1F'];
    emojiAnimation.innerHTML = sparkles.map(function(e) {
        return '<span class="sparkle">' + e + '</span>';
    }).join(' ');

    fetch('/download_photo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            imageUrl: document.getElementById('photo').src,
            quote: document.getElementById('quote').textContent,
            photoCredit: document.getElementById('photoCredit').textContent
        })
    })
    .then(function(response) {
        if (!response.ok) {
            throw new Error('HTTP error! Status: ' + response.status);
        }
        return response.blob();
    })
    .then(function(blob) {
        clearInterval(messageInterval);
        loadingMessage.textContent = '\u2728\u2728 Download Complete \u2728\u2728';
        emojiAnimation.innerHTML = '';

        var url = window.URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        a.download = 'virtual-sparkle.png';
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();

        setTimeout(function() {
            statusBox.style.opacity = '0';
            setTimeout(function() {
                statusBox.style.display = 'none';
            }, 300);
        }, 2000);
    })
    .catch(function(error) {
        console.error('Download error:', error);
        clearInterval(messageInterval);
        loadingMessage.textContent = '\u274C Oops! Something went wrong.';
        emojiAnimation.innerHTML = '\uD83D\uDE22\uD83D\uDC94';

        setTimeout(function() {
            statusBox.style.opacity = '0';
            setTimeout(function() {
                statusBox.style.display = 'none';
            }, 300);
        }, 3000);
    });
});

// Desktop-only tooltips
if (!/Mobi|Android/i.test(navigator.userAgent)) {
    var heartButton = document.getElementById('heartButton');
    var downloadButton = document.getElementById('downloadButton');
    var tooltipTimeout;

    heartButton.addEventListener('mouseover', function(event) {
        tooltipTimeout = setTimeout(function() {
            tooltip.textContent = heartButton.dataset.tooltip;
            tooltip.style.display = 'block';
            tooltip.style.left = event.pageX + 10 + 'px';
            tooltip.style.top = event.pageY + 10 + 'px';
        }, 500);
    });
    heartButton.addEventListener('mouseout', function() {
        clearTimeout(tooltipTimeout);
        tooltip.style.display = 'none';
    });
    heartButton.addEventListener('mousemove', function(event) {
        tooltip.style.left = event.pageX + 10 + 'px';
        tooltip.style.top = event.pageY + 10 + 'px';
    });

    var downloadTooltipTimeout;
    downloadButton.addEventListener('mouseover', function(event) {
        downloadTooltipTimeout = setTimeout(function() {
            tooltip.textContent = downloadButton.dataset.tooltip;
            tooltip.style.display = 'block';
            tooltip.style.left = event.pageX + 10 + 'px';
            tooltip.style.top = event.pageY + 10 + 'px';
        }, 500);
    });
    downloadButton.addEventListener('mouseout', function() {
        clearTimeout(downloadTooltipTimeout);
        tooltip.style.display = 'none';
    });
    downloadButton.addEventListener('mousemove', function(event) {
        tooltip.style.left = event.pageX + 10 + 'px';
        tooltip.style.top = event.pageY + 10 + 'px';
    });
}
