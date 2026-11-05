document.addEventListener('DOMContentLoaded', () => {
  // Determine API base URL:
  // - When opened via http:// or https:// (localhost, Cloudflare Tunnel, or any public domain),
  //   always use relative paths ('') so requests stay on the same secure origin.
  // - Only when opened directly as a local file (file://) does it point to http://127.0.0.1:5500.
  let API_BASE = (window.location.protocol === 'file:') 
    ? 'http://127.0.0.1:5500' 
    : '';

  // Show a helpful banner if opened as file:///
  if (window.location.protocol === 'file:') {
    const banner = document.createElement('div');
    banner.style.cssText = 'background: linear-gradient(90deg, #ff5500, #38bdf8); color: #0b0f17; font-weight: 700; padding: 10px 16px; text-align: center; font-size: 13.5px; position: sticky; top: 0; z-index: 9999; box-shadow: 0 4px 12px rgba(0,0,0,0.3);';
    banner.innerHTML = '⚡ Mẹo: Để tải mượt mà nhất, hãy mở bằng đường link máy chủ: <a href="http://localhost:5500" target="_blank" style="color: #000; text-decoration: underline; font-weight: 800;">http://localhost:5500</a> hoặc <a href="http://127.0.0.1:5500" target="_blank" style="color: #000; text-decoration: underline; font-weight: 800;">http://127.0.0.1:5500</a>';
    document.body.prepend(banner);
  }

  // DOM Elements - Main & URL Form
  const urlForm = document.getElementById('urlForm');
  const urlInput = document.getElementById('urlInput');
  const clearBtn = document.getElementById('clearBtn');
  const pasteBtn = document.getElementById('pasteBtn');
  const fetchBtn = document.getElementById('fetchBtn');
  const btnText = fetchBtn.querySelector('.btn-text');
  const btnIcon = fetchBtn.querySelector('.btn-icon');
  const btnSpinner = fetchBtn.querySelector('.btn-spinner');
  const inputIcon = document.getElementById('inputIcon');

  const tabBtns = document.querySelectorAll('.tab-btn');
  const sampleChips = document.querySelectorAll('.sample-chip');
  const statusAlert = document.getElementById('statusAlert');
  const alertMessage = document.getElementById('alertMessage');
  const alertClose = document.getElementById('alertClose');

  const resultContainer = document.getElementById('resultContainer');
  const mediaThumbnail = document.getElementById('mediaThumbnail');
  const mediaDuration = document.getElementById('mediaDuration');
  const mediaPlatformBadge = document.getElementById('mediaPlatformBadge');
  const mediaTypeTag = document.getElementById('mediaTypeTag');
  const mediaTitle = document.getElementById('mediaTitle');
  const mediaAuthor = document.getElementById('mediaAuthor');
  const mediaExtra = document.getElementById('mediaExtra');

  const modeBtns = document.querySelectorAll('.mode-btn');
  const videoModeBtn = document.getElementById('videoModeBtn');
  const thumbnailModeBtn = document.getElementById('thumbnailModeBtn');
  const audioOptionsPanel = document.getElementById('audioOptionsPanel');
  const videoOptionsPanel = document.getElementById('videoOptionsPanel');
  const thumbnailOptionsPanel = document.getElementById('thumbnailOptionsPanel');
  const thumbQuickBtn = document.getElementById('thumbQuickBtn');

  const audioQualityCards = document.querySelectorAll('#audioQualityGrid .quality-card');
  const videoQualityCards = document.querySelectorAll('#videoQualityGrid .quality-card');
  const thumbQualityCards = document.querySelectorAll('#thumbQualityGrid .quality-card');

  const playlistSection = document.getElementById('playlistSection');
  const playlistTotal = document.getElementById('playlistTotal');
  const playlistItems = document.getElementById('playlistItems');
  const selectAllTracksBtn = document.getElementById('selectAllTracksBtn');
  const deselectAllTracksBtn = document.getElementById('deselectAllTracksBtn');

  const downloadBtn = document.getElementById('downloadBtn');
  const downloadBtnText = document.getElementById('downloadBtnText');
  const progressCancelBtn = document.getElementById('progressCancelBtn');

  const progressBox = document.getElementById('progressBox');
  const progressStatus = document.getElementById('progressStatus');
  const progressPercent = document.getElementById('progressPercent');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressSpeed = document.getElementById('progressSpeed');
  const progressETA = document.getElementById('progressETA');
  const fileDownloadLink = document.getElementById('fileDownloadLink');

  const backendStatus = document.getElementById('backendStatus');
  const serverStatusText = document.getElementById('serverStatusText');

  // Inline Audio Preview Player Elements
  const audioPlayerWrapper = document.getElementById('audioPlayerWrapper');
  const globalAudioPlayer = document.getElementById('globalAudioPlayer');
  const playerPlayBtn = document.getElementById('playerPlayBtn');
  const playerPlayIcon = document.getElementById('playerPlayIcon');
  const playerSpinner = document.getElementById('playerSpinner');
  const playerStatusText = document.getElementById('playerStatusText');
  const playerCurrentTime = document.getElementById('playerCurrentTime');
  const playerTotalTime = document.getElementById('playerTotalTime');
  const playerProgressContainer = document.getElementById('playerProgressContainer');
  const playerProgressBuffered = document.getElementById('playerProgressBuffered');
  const playerProgressFill = document.getElementById('playerProgressFill');
  const playerMuteBtn = document.getElementById('playerMuteBtn');
  const playerMuteIcon = document.getElementById('playerMuteIcon');
  const playerVolumeSlider = document.getElementById('playerVolumeSlider');

  let activePlaylistPlayBtn = null;

  function resetAudioPlayer() {
    if (globalAudioPlayer) {
      globalAudioPlayer.pause();
      globalAudioPlayer.removeAttribute('src');
      globalAudioPlayer.load();
    }
    if (playerPlayBtn) playerPlayBtn.classList.remove('playing');
    if (playerPlayIcon) {
      playerPlayIcon.className = 'fa-solid fa-play';
      playerPlayIcon.classList.remove('hidden');
    }
    if (playerSpinner) playerSpinner.classList.add('hidden');
    if (playerCurrentTime) playerCurrentTime.textContent = '00:00';
    if (playerTotalTime) playerTotalTime.textContent = '00:00';
    if (playerProgressFill) playerProgressFill.style.width = '0%';
    if (playerProgressBuffered) playerProgressBuffered.style.width = '0%';
    if (playerStatusText) playerStatusText.textContent = 'Nghe trực tiếp';
    if (activePlaylistPlayBtn) {
      activePlaylistPlayBtn.classList.remove('playing');
      activePlaylistPlayBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
      activePlaylistPlayBtn = null;
    }
  }

  function setupAudioTrack(streamUrl, duration, label) {
    if (!globalAudioPlayer) return;
    resetAudioPlayer();
    globalAudioPlayer.src = streamUrl;
    if (duration && duration > 0) {
      playerTotalTime.textContent = formatDuration(duration);
    }
    if (label) {
      playerStatusText.textContent = label;
    }
  }

  if (globalAudioPlayer) {
    globalAudioPlayer.addEventListener('waiting', () => {
      if (playerPlayIcon) playerPlayIcon.classList.add('hidden');
      if (playerSpinner) playerSpinner.classList.remove('hidden');
    });

    globalAudioPlayer.addEventListener('playing', () => {
      if (playerPlayIcon) {
        playerPlayIcon.className = 'fa-solid fa-pause';
        playerPlayIcon.classList.remove('hidden');
      }
      if (playerSpinner) playerSpinner.classList.add('hidden');
      if (playerPlayBtn) playerPlayBtn.classList.add('playing');
    });

    globalAudioPlayer.addEventListener('pause', () => {
      if (playerPlayIcon) {
        playerPlayIcon.className = 'fa-solid fa-play';
        playerPlayIcon.classList.remove('hidden');
      }
      if (playerSpinner) playerSpinner.classList.add('hidden');
      if (playerPlayBtn) playerPlayBtn.classList.remove('playing');
      if (activePlaylistPlayBtn) {
        activePlaylistPlayBtn.classList.remove('playing');
        activePlaylistPlayBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
      }
    });

    globalAudioPlayer.addEventListener('timeupdate', () => {
      if (!globalAudioPlayer.duration) return;
      const curr = globalAudioPlayer.currentTime;
      const dur = globalAudioPlayer.duration;
      playerCurrentTime.textContent = formatDuration(curr);
      if (dur && isFinite(dur)) {
        playerTotalTime.textContent = formatDuration(dur);
        const percent = (curr / dur) * 100;
        playerProgressFill.style.width = `${percent}%`;
      }
    });

    globalAudioPlayer.addEventListener('progress', () => {
      if (globalAudioPlayer.buffered.length > 0 && globalAudioPlayer.duration) {
        const bufferedEnd = globalAudioPlayer.buffered.end(globalAudioPlayer.buffered.length - 1);
        const dur = globalAudioPlayer.duration;
        if (dur && isFinite(dur)) {
          const percent = (bufferedEnd / dur) * 100;
          playerProgressBuffered.style.width = `${percent}%`;
        }
      }
    });

    globalAudioPlayer.addEventListener('ended', () => {
      resetAudioPlayer();
    });

    globalAudioPlayer.addEventListener('error', (e) => {
      console.warn('Audio streaming error:', e);
      if (playerPlayIcon) {
        playerPlayIcon.className = 'fa-solid fa-triangle-exclamation';
        playerPlayIcon.classList.remove('hidden');
      }
      if (playerSpinner) playerSpinner.classList.add('hidden');
      if (playerPlayBtn) playerPlayBtn.classList.remove('playing');
      if (playerStatusText) playerStatusText.textContent = 'Lỗi phát nhạc';
    });
  }

  if (playerPlayBtn) {
    playerPlayBtn.addEventListener('click', () => {
      if (!globalAudioPlayer) return;
      if (!globalAudioPlayer.src) {
        if (currentMediaData && currentMediaData.stream_url) {
          setupAudioTrack(currentMediaData.stream_url, currentMediaData.duration, 'Nghe trực tiếp');
        }
      }
      if (globalAudioPlayer.paused) {
        globalAudioPlayer.play().catch(err => {
          console.warn('Playback error:', err);
        });
      } else {
        globalAudioPlayer.pause();
      }
    });
  }

  // Scrubber Seek (Click or scrub on progress bar)
  if (playerProgressContainer) {
    playerProgressContainer.addEventListener('click', (e) => {
      if (!globalAudioPlayer || !globalAudioPlayer.duration || !isFinite(globalAudioPlayer.duration)) return;
      const rect = playerProgressContainer.getBoundingClientRect();
      const clickX = e.clientX - rect.left;
      const fraction = Math.max(0, Math.min(1, clickX / rect.width));
      globalAudioPlayer.currentTime = fraction * globalAudioPlayer.duration;
    });
  }

  // Volume & Mute Controls
  function updateMuteIcon() {
    if (!playerMuteIcon || !globalAudioPlayer) return;
    if (globalAudioPlayer.muted || globalAudioPlayer.volume === 0) {
      playerMuteIcon.className = 'fa-solid fa-volume-xmark';
    } else if (globalAudioPlayer.volume < 0.5) {
      playerMuteIcon.className = 'fa-solid fa-volume-low';
    } else {
      playerMuteIcon.className = 'fa-solid fa-volume-high';
    }
  }

  if (playerVolumeSlider && globalAudioPlayer) {
    playerVolumeSlider.addEventListener('input', (e) => {
      const val = parseFloat(e.target.value);
      globalAudioPlayer.volume = val;
      globalAudioPlayer.muted = (val === 0);
      updateMuteIcon();
    });
  }

  if (playerMuteBtn && globalAudioPlayer) {
    playerMuteBtn.addEventListener('click', () => {
      globalAudioPlayer.muted = !globalAudioPlayer.muted;
      updateMuteIcon();
    });
  }

  // Application State
  let currentPlatform = 'youtube'; // 'youtube', 'spotify', 'soundcloud'
  let currentMode = 'audio';      // 'audio', 'video', 'thumbnail'
  let currentAudioFormat = 'mp3';
  let currentAudioQuality = '320';
  let currentVideoFormat = 'mp4';
  let currentVideoQuality = '1080';
  let currentThumbFormat = 'jpg';
  let currentMediaData = null;
  let activeDownloadJobId = null;
  let progressPollingInterval = null;

  // Smart fetch helper with automatic 127.0.0.1 / localhost fallback
  async function apiFetch(path, options = {}) {
    try {
      return await fetch(`${API_BASE}${path}`, options);
    } catch (err) {
      if (API_BASE === 'http://127.0.0.1:5500') {
        API_BASE = 'http://localhost:5500';
        return await fetch(`${API_BASE}${path}`, options);
      } else if (API_BASE === 'http://localhost:5500') {
        API_BASE = 'http://127.0.0.1:5500';
        return await fetch(`${API_BASE}${path}`, options);
      }
      throw err;
    }
  }

  // Initialize Backend Ping
  checkServerHealth();
  setInterval(checkServerHealth, 8000);

  // Platform Filter Tab Switch
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentPlatform = btn.dataset.platform;
      updateInputPlaceholder();
    });
  });

  function updateInputPlaceholder() {
    const inputWrap = document.querySelector('.input-wrapper');
    if (inputWrap) {
      inputWrap.setAttribute('data-platform', currentPlatform);
    }

    if (currentPlatform === 'tiktok') {
      urlInput.placeholder = 'Dán link TikTok (Video không logo, Âm thanh)...';
      inputIcon.className = 'fa-brands fa-tiktok';
      inputIcon.style.color = '#25f4ee';
    } else if (currentPlatform === 'spotify') {
      urlInput.placeholder = 'Dán link Spotify (Bài hát, Album, hoặc Playlist)...';
      inputIcon.className = 'fa-brands fa-spotify';
      inputIcon.style.color = '#1ed760';
    } else if (currentPlatform === 'soundcloud') {
      urlInput.placeholder = 'Dán link SoundCloud (Bài hát đơn hoặc Playlist / Sets)...';
      inputIcon.className = 'fa-brands fa-soundcloud';
      inputIcon.style.color = '#ff5500';
    } else if (currentPlatform === 'zingmp3') {
      urlInput.placeholder = 'Dán link Zing MP3 (Bài hát, Video, Album)...';
      inputIcon.className = 'fa-solid fa-compact-disc';
      inputIcon.style.color = '#a855f7';
    } else if (currentPlatform === 'nhaccuatui') {
      urlInput.placeholder = 'Dán link NhacCuaTui (Bài hát, Playlist)...';
      inputIcon.className = 'fa-solid fa-cloud-arrow-down';
      inputIcon.style.color = '#00bcd4';
    } else {
      urlInput.placeholder = 'Dán link YouTube (Video, Short, hoặc Playlist)...';
      inputIcon.className = 'fa-brands fa-youtube';
      inputIcon.style.color = '#ff334b';
    }
  }

  // Initial call to set platform attribute
  updateInputPlaceholder();

  function toggleClearBtn() {
    if (clearBtn) {
      if (urlInput.value && urlInput.value.trim().length > 0) {
        clearBtn.classList.remove('hidden');
      } else {
        clearBtn.classList.add('hidden');
      }
    }
  }

  // Auto detect input change and sync active tab
  urlInput.addEventListener('input', () => {
    toggleClearBtn();
    const val = urlInput.value.trim().toLowerCase();
    if (val.includes('tiktok.com') || val.includes('douyin.com')) {
      inputIcon.className = 'fa-brands fa-tiktok';
      inputIcon.style.color = '#25f4ee';
      currentPlatform = 'tiktok';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'tiktok'));
      updateInputPlaceholder();
    } else if (val.includes('youtube.com') || val.includes('youtu.be')) {
      inputIcon.className = 'fa-brands fa-youtube';
      inputIcon.style.color = '#ff334b';
      currentPlatform = 'youtube';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'youtube'));
      updateInputPlaceholder();
    } else if (val.includes('spotify.com') || val.includes('spotify:')) {
      inputIcon.className = 'fa-brands fa-spotify';
      inputIcon.style.color = '#1ed760';
      currentPlatform = 'spotify';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'spotify'));
      updateInputPlaceholder();
    } else if (val.includes('soundcloud.com') || val.includes('on.soundcloud.com')) {
      inputIcon.className = 'fa-brands fa-soundcloud';
      inputIcon.style.color = '#ff5500';
      currentPlatform = 'soundcloud';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'soundcloud'));
      updateInputPlaceholder();
    } else if (val.includes('zingmp3.vn') || val.includes('mp3.zing.vn')) {
      inputIcon.className = 'fa-solid fa-compact-disc';
      inputIcon.style.color = '#a855f7';
      currentPlatform = 'zingmp3';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'zingmp3'));
      updateInputPlaceholder();
    } else if (val.includes('nhaccuatui.com') || val.includes('nct.vn')) {
      inputIcon.className = 'fa-solid fa-cloud-arrow-down';
      inputIcon.style.color = '#00bcd4';
      currentPlatform = 'nhaccuatui';
      tabBtns.forEach(b => b.classList.toggle('active', b.dataset.platform === 'nhaccuatui'));
      updateInputPlaceholder();
    } else if (!val) {
      updateInputPlaceholder();
    }
  });

  // Clear button click
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      urlInput.value = '';
      toggleClearBtn();
      updateInputPlaceholder();
      urlInput.focus();
    });
  }

  // Initial check on load in case browser retained input text
  toggleClearBtn();

  // ==================== CORNER TOAST NOTIFICATIONS ====================
  const toastContainer = document.getElementById('toastContainer');

  function showToast(msg, type = 'info', title = null, isBotError = false, duration = null) {
    if (!toastContainer) return null;

    let defaultTitle = 'Thông báo';
    let iconClass = 'fa-solid fa-circle-info';
    let autoDismissTime = 4500;

    if (type === 'success') {
      defaultTitle = 'Thành công';
      iconClass = 'fa-solid fa-circle-check';
      autoDismissTime = 4000;
    } else if (type === 'error') {
      defaultTitle = isBotError ? 'Bảo vệ YouTube' : 'Có lỗi xảy ra';
      iconClass = 'fa-solid fa-circle-exclamation';
      autoDismissTime = 8000;
    } else if (type === 'warning') {
      defaultTitle = 'Lưu ý';
      iconClass = 'fa-solid fa-triangle-exclamation';
      autoDismissTime = 6000;
    } else if (type === 'loading') {
      defaultTitle = 'Đang xử lý';
      iconClass = 'fa-solid fa-spinner fa-spin';
      autoDismissTime = 0;
    }

    const toastTitle = title || defaultTitle;
    if (duration !== null) autoDismissTime = duration;

    const toast = document.createElement('div');
    toast.className = `toast-card toast-${type}`;
    toast.setAttribute('role', 'alert');

    let botActionHtml = '';
    if (isBotError) {
      botActionHtml = `
        <div class="toast-action-row">
          <button type="button" class="toast-btn-action" id="toastCookieBtn">
            <i class="fa-solid fa-cookie-bite"></i> Cài đặt Cookie ngay
          </button>
        </div>`;
    }

    toast.innerHTML = `
      <div class="toast-glow"></div>
      <div class="toast-icon-wrap">
        <i class="${iconClass}"></i>
      </div>
      <div class="toast-body">
        <div class="toast-header-row">
          <span class="toast-title">${escapeHtml(toastTitle)}</span>
          <button type="button" class="toast-close" title="Đóng">&times;</button>
        </div>
        <div class="toast-message">${escapeHtml(msg)}${botActionHtml}</div>
      </div>
      ${autoDismissTime > 0 ? `<div class="toast-progress-bar" style="animation-duration: ${autoDismissTime}ms"></div>` : ''}
    `;

    toastContainer.appendChild(toast);

    const closeBtn = toast.querySelector('.toast-close');
    let dismissTimeout = null;
    let isDismissed = false;

    function dismiss() {
      if (isDismissed) return;
      isDismissed = true;
      if (dismissTimeout) clearTimeout(dismissTimeout);
      toast.classList.add('dismissed');
      setTimeout(() => {
        if (toast.parentNode) toast.parentNode.removeChild(toast);
      }, 350);
    }

    if (closeBtn) {
      closeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dismiss();
      });
    }

    const cookieBtn = toast.querySelector('#toastCookieBtn');
    if (cookieBtn) {
      cookieBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dismiss();
        if (typeof openCookieModal === 'function') openCookieModal();
      });
    }

    if (autoDismissTime > 0) {
      let remaining = autoDismissTime;
      let start = Date.now();

      const startTimer = () => {
        start = Date.now();
        dismissTimeout = setTimeout(dismiss, remaining);
      };

      const pauseTimer = () => {
        if (dismissTimeout) {
          clearTimeout(dismissTimeout);
          remaining -= Date.now() - start;
        }
        const bar = toast.querySelector('.toast-progress-bar');
        if (bar) bar.style.animationPlayState = 'paused';
      };

      const resumeTimer = () => {
        startTimer();
        const bar = toast.querySelector('.toast-progress-bar');
        if (bar) bar.style.animationPlayState = 'running';
      };

      toast.addEventListener('mouseenter', pauseTimer);
      toast.addEventListener('mouseleave', resumeTimer);
      startTimer();
    }

    return { dismiss, element: toast };
  }

  function showAlert(msg, type = 'info', isBotError = false, title = null) {
    if (!msg) return;
    showToast(msg, type, title, isBotError);
  }

  // Paste button
  pasteBtn.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        urlInput.value = text.trim();
        urlInput.dispatchEvent(new Event('input'));
        showAlert('Đã dán liên kết thành công!', 'success', false, 'Dán liên kết');
      }
    } catch (err) {
      showAlert('Không thể truy cập Clipboard. Vui lòng bấm Ctrl+V để dán.', 'error', false, 'Lỗi Clipboard');
    }
  });

  // Listen to keyboard Ctrl+V / paste in urlInput
  urlInput.addEventListener('paste', () => {
    setTimeout(() => {
      if (urlInput.value.trim()) {
        showAlert('Đã dán liên kết thành công!', 'success', false, 'Dán liên kết');
      }
    }, 50);
  });

  // Quick Samples
  sampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      urlInput.value = chip.dataset.sample;
      urlInput.dispatchEvent(new Event('input'));
      urlForm.dispatchEvent(new Event('submit'));
    });
  });

  // Alert Close (Legacy statusAlert backward compatibility)
  if (alertClose && statusAlert) {
    alertClose.addEventListener('click', () => {
      statusAlert.classList.add('hidden');
    });
  }

  // Mode Toggle (Audio / Video / Thumbnail)
  modeBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      const mode = btn.dataset.mode;
      if (mode === 'video' && currentMediaData && (currentMediaData.platform === 'spotify' || currentMediaData.platform === 'soundcloud')) {
        showAlert('Spotify và SoundCloud là nền tảng âm thanh. Vui lòng chọn chế độ Âm thanh (Audio) hoặc Ảnh bìa (Thumbnail)!', 'info');
        return;
      }
      modeBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentMode = mode;

      if (audioOptionsPanel) audioOptionsPanel.classList.toggle('hidden', currentMode !== 'audio');
      if (videoOptionsPanel) videoOptionsPanel.classList.toggle('hidden', currentMode !== 'video');
      if (thumbnailOptionsPanel) thumbnailOptionsPanel.classList.toggle('hidden', currentMode !== 'thumbnail');
      updateDownloadBtnLabel();
    });
  });

  // Quality Selection - Audio
  audioQualityCards.forEach(card => {
    card.addEventListener('click', () => {
      audioQualityCards.forEach(c => {
        c.classList.remove('active');
        c.querySelector('.card-radio i').className = 'fa-regular fa-circle';
      });
      card.classList.add('active');
      card.querySelector('.card-radio i').className = 'fa-solid fa-circle-check';
      currentAudioFormat = card.dataset.format;
      currentAudioQuality = card.dataset.quality;
      updateDownloadBtnLabel();
    });
  });

  // Quality Selection - Video
  videoQualityCards.forEach(card => {
    card.addEventListener('click', () => {
      videoQualityCards.forEach(c => {
        c.classList.remove('active');
        c.querySelector('.card-radio i').className = 'fa-regular fa-circle';
      });
      card.classList.add('active');
      card.querySelector('.card-radio i').className = 'fa-solid fa-circle-check';
      currentVideoFormat = card.dataset.format;
      currentVideoQuality = card.dataset.quality;
      updateDownloadBtnLabel();
    });
  });

  // Quality Selection - Thumbnail
  thumbQualityCards.forEach(card => {
    card.addEventListener('click', () => {
      thumbQualityCards.forEach(c => {
        c.classList.remove('active');
        c.querySelector('.card-radio i').className = 'fa-regular fa-circle';
      });
      card.classList.add('active');
      card.querySelector('.card-radio i').className = 'fa-solid fa-circle-check';
      currentThumbFormat = card.dataset.format || 'jpg';
      updateDownloadBtnLabel();
    });
  });

  function updateDownloadBtnLabel() {
    if (currentMode === 'audio') {
      const qText = currentAudioQuality === '320' ? '320kbps Studio' : 
                    currentAudioQuality === 'lossless' ? 'Lossless FLAC' :
                    currentAudioQuality === 'best' ? 'Original Best' :
                    currentAudioQuality === 'master' ? 'WAV Master' : '256kbps';
      downloadBtnText.textContent = `Tải Âm thanh (${currentAudioFormat.toUpperCase()} - ${qText})`;
    } else if (currentMode === 'video') {
      if (currentMediaData && currentMediaData.platform === 'tiktok') {
        downloadBtnText.textContent = 'Tải Video TikTok Không Logo (MP4 HD)';
      } else {
        const vText = currentVideoQuality === '2160' ? '4K 2160p' :
                      currentVideoQuality === '1440' ? '2K 1440p' :
                      currentVideoQuality === '1080' ? 'Full HD 1080p' : '720p HD';
        downloadBtnText.textContent = `Tải Video (${vText} MP4)`;
      }
    } else if (currentMode === 'thumbnail') {
      const tText = currentThumbFormat === 'jpg' ? 'JPG Ultra HD' :
                    currentThumbFormat === 'png' ? 'PNG Lossless' : 'File ảnh gốc từ Server';
      downloadBtnText.textContent = `Tải Ảnh Thumbnail (${tText})`;
    }
  }

  // Helper: Direct Download Thumbnail
  function downloadThumbnail(format = 'jpg') {
    if (!currentMediaData || !currentMediaData.thumbnail) {
      showAlert('Chưa tìm thấy ảnh bìa từ nguồn này!', 'error');
      return;
    }

    const dlUrl = `${API_BASE}/api/thumbnail/download?url=${encodeURIComponent(currentMediaData.thumbnail)}&title=${encodeURIComponent(currentMediaData.title)}&format=${encodeURIComponent(format)}`;
    
    const hiddenIframe = document.createElement('iframe');
    hiddenIframe.style.display = 'none';
    hiddenIframe.src = dlUrl;
    document.body.appendChild(hiddenIframe);
    setTimeout(() => hiddenIframe.remove(), 10000);

    showAlert(`Đang tải ảnh Thumbnail (${format.toUpperCase()}) chất lượng cao nhất...`, 'success', false, 'Tải Thumbnail');
  }

  // Quick Thumbnail Download button on image card
  if (thumbQuickBtn) {
    thumbQuickBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      downloadThumbnail('jpg');
    });
  }

  // Form Submit: Fetch Info (URL Mode)
  urlForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    let url = urlInput.value.trim();
    if (!url) return;

    if (!url.startsWith('http://') && !url.startsWith('https://') && !url.startsWith('spotify:')) {
      url = 'https://' + url;
      urlInput.value = url;
    }

    setFetchLoading(true);
    if (statusAlert) statusAlert.classList.add('hidden');
    resultContainer.classList.add('hidden');
    progressBox.classList.add('hidden');
    resetAudioPlayer();
    showAlert('Đang phân tích liên kết, vui lòng chờ trong giây lát...', 'info', false, 'Đang phân tích');

    try {
      const response = await apiFetch('/api/info', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ url })
      });

      let data;
      const responseText = await response.text();
      try {
        data = JSON.parse(responseText);
      } catch (parseErr) {
        throw new Error(
          'Không thể phân tích phản hồi từ máy chủ. Vui lòng đảm bảo server (app.py) đang hoạt động!'
        );
      }

      if (!response.ok || !data.success) {
        if (data && data.is_bot_error) {
          showAlert(data.error, 'error', true, 'Bảo vệ YouTube');
          return;
        }
        throw new Error(data.error || 'Không thể lấy thông tin từ liên kết này. Vui lòng kiểm tra lại!');
      }

      renderMediaInfo(data);
      resultContainer.classList.remove('hidden');
      resultContainer.scrollIntoView({ behavior: 'smooth', block: 'start' });
      const mediaTitle = data.title || 'Nội dung đa phương tiện';
      showAlert(`Đã nhận diện: ${mediaTitle.length > 40 ? mediaTitle.slice(0, 37) + '...' : mediaTitle}`, 'success', false, 'Nhận diện thành công');
    } catch (err) {
      console.error(err);
      if (err.message && err.message.includes('Failed to fetch')) {
        if (window.location.protocol === 'file:') {
          showAlert('Trình duyệt đang chặn kết nối file nội bộ. Hãy mở trang web trực tiếp tại: http://localhost:5500', 'error');
        } else {
          showAlert('Không thể kết nối đến máy chủ backend (app.py). Hãy chắc chắn bạn đã chạy server trước khi tải!', 'error');
        }
      } else {
        showAlert(err.message, 'error');
      }
    } finally {
      setFetchLoading(false);
    }
  });

  function setFetchLoading(isLoading) {
    if (isLoading) {
      fetchBtn.disabled = true;
      btnText.textContent = 'Đang kiểm tra...';
      btnIcon.classList.add('hidden');
      btnSpinner.classList.remove('hidden');
    } else {
      fetchBtn.disabled = false;
      btnText.textContent = 'Kiểm tra';
      btnIcon.classList.remove('hidden');
      btnSpinner.classList.add('hidden');
    }
  }

  function renderMediaInfo(data) {
    currentMediaData = data;

    mediaThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?w=600';
    mediaDuration.textContent = formatDuration(data.duration);
    mediaTitle.textContent = data.title || 'Không có tiêu đề';
    
    if (data.extra) {
      mediaExtra.querySelector('span').textContent = data.extra;
      mediaExtra.classList.remove('hidden');
    } else {
      mediaExtra.classList.add('hidden');
    }

    if (data.platform === 'tiktok') {
      mediaPlatformBadge.className = 'platform-indicator tiktok';
      mediaPlatformBadge.innerHTML = '<i class="fa-brands fa-tiktok"></i>';
      mediaTypeTag.textContent = 'TikTok Video (Không Logo)';
      mediaAuthor.querySelector('span').textContent = data.author || 'TikTok Creator';
      if (videoModeBtn) videoModeBtn.style.display = 'flex';
    } else if (data.platform === 'youtube') {
      mediaPlatformBadge.className = 'platform-indicator youtube';
      mediaPlatformBadge.innerHTML = '<i class="fa-brands fa-youtube"></i>';
      mediaTypeTag.textContent = data.is_playlist ? 'YouTube Playlist' : (data.is_short ? 'YouTube Short' : 'YouTube Video');
      mediaAuthor.querySelector('span').textContent = data.author || 'YouTube Channel';
      if (videoModeBtn) videoModeBtn.style.display = 'flex';
    } else if (data.platform === 'soundcloud') {
      mediaPlatformBadge.className = 'platform-indicator soundcloud';
      mediaPlatformBadge.innerHTML = '<i class="fa-brands fa-soundcloud"></i>';
      mediaTypeTag.textContent = data.is_playlist ? 'SoundCloud Playlist' : 'SoundCloud Track';
      mediaAuthor.querySelector('span').textContent = data.author || 'SoundCloud Artist';
      if (videoModeBtn) videoModeBtn.style.display = 'none';
      if (currentMode === 'video' && modeBtns[0]) modeBtns[0].click();
    } else if (data.platform === 'zingmp3') {
      mediaPlatformBadge.className = 'platform-indicator zingmp3';
      mediaPlatformBadge.innerHTML = '<i class="fa-solid fa-compact-disc"></i>';
      mediaTypeTag.textContent = data.is_playlist ? 'Zing MP3 Playlist' : 'Zing MP3 Track';
      mediaAuthor.querySelector('span').textContent = data.author || 'Zing MP3 Artist';
      if (videoModeBtn) videoModeBtn.style.display = 'none';
      if (currentMode === 'video' && modeBtns[0]) modeBtns[0].click();
    } else if (data.platform === 'nhaccuatui') {
      mediaPlatformBadge.className = 'platform-indicator nhaccuatui';
      mediaPlatformBadge.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i>';
      mediaTypeTag.textContent = data.is_playlist ? 'NhacCuaTui Playlist' : 'NhacCuaTui Track';
      mediaAuthor.querySelector('span').textContent = data.author || 'NhacCuaTui Artist';
      if (videoModeBtn) videoModeBtn.style.display = 'none';
      if (currentMode === 'video' && modeBtns[0]) modeBtns[0].click();
    } else {
      mediaPlatformBadge.className = 'platform-indicator spotify';
      mediaPlatformBadge.innerHTML = '<i class="fa-brands fa-spotify"></i>';
      mediaTypeTag.textContent = data.is_playlist ? 'Spotify Playlist' : (data.is_album ? 'Spotify Album' : 'Spotify Track');
      mediaAuthor.querySelector('span').textContent = data.author || 'Spotify Artist';
      if (videoModeBtn) videoModeBtn.style.display = 'none';
      if (currentMode === 'video' && modeBtns[0]) modeBtns[0].click();
    }

    // Direct Audio Preview Setup
    if (data.stream_url) {
      setupAudioTrack(data.stream_url, data.duration, data.is_playlist ? 'Xem trước danh sách' : 'Nghe trực tiếp');
    } else {
      resetAudioPlayer();
    }

    if (data.is_playlist && data.tracks && data.tracks.length > 0) {
      playlistTotal.textContent = data.tracks.length;
      playlistItems.innerHTML = '';
      data.tracks.forEach((track, idx) => {
        const item = document.createElement('div');
        item.className = 'playlist-item';
        item.innerHTML = `
          <input type="checkbox" id="track_${idx}" value="${idx}" checked>
          <button type="button" class="playlist-play-btn" data-track-idx="${idx}" title="Nghe trực tiếp bài này">
            <i class="fa-solid fa-play"></i>
          </button>
          <label for="track_${idx}" class="playlist-item-title">${idx + 1}. ${escapeHtml(track.title)} - <span style="color:var(--text-muted)">${escapeHtml(track.author || '')}</span></label>
          <span class="playlist-item-dur">${formatDuration(track.duration)}</span>
        `;
        const playBtn = item.querySelector('.playlist-play-btn');
        if (playBtn) {
          playBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            if (activePlaylistPlayBtn === playBtn && !globalAudioPlayer.paused) {
              globalAudioPlayer.pause();
              playBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
              playBtn.classList.remove('playing');
              activePlaylistPlayBtn = null;
            } else {
              if (activePlaylistPlayBtn) {
                activePlaylistPlayBtn.innerHTML = '<i class="fa-solid fa-play"></i>';
                activePlaylistPlayBtn.classList.remove('playing');
              }
              activePlaylistPlayBtn = playBtn;
              playBtn.classList.add('playing');
              playBtn.innerHTML = '<i class="fa-solid fa-pause"></i>';
              const tUrl = track.stream_url || `/api/stream?url=${encodeURIComponent(track.url || '')}`;
              const tLabel = track.title && track.title.length > 28 ? track.title.slice(0, 28) + '...' : (track.title || 'Bài hát');
              setupAudioTrack(tUrl, track.duration, tLabel);
              globalAudioPlayer.play().catch(console.warn);
            }
          });
        }
        playlistItems.appendChild(item);
      });
      playlistSection.classList.remove('hidden');
    } else {
      playlistSection.classList.add('hidden');
    }

    updateDownloadBtnLabel();
  }

  // Playlist Controls
  selectAllTracksBtn.addEventListener('click', () => {
    playlistItems.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
  });

  deselectAllTracksBtn.addEventListener('click', () => {
    playlistItems.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
  });

  // Download Trigger (URL mode)
  downloadBtn.addEventListener('click', async () => {
    if (!currentMediaData) {
      showAlert('Vui lòng kiểm tra liên kết trước khi tải!', 'error');
      return;
    }

    // Direct Thumbnail Download Mode
    if (currentMode === 'thumbnail') {
      downloadThumbnail(currentThumbFormat);
      return;
    }

    let selectedTrackIndices = [];
    let selectedTracksData = [];
    if (currentMediaData.is_playlist && currentMediaData.tracks) {
      const checked = playlistItems.querySelectorAll('input[type="checkbox"]:checked');
      if (checked.length === 0) {
        showAlert('Vui lòng chọn ít nhất 1 bài hát trong danh sách phát để tải!', 'error');
        return;
      }
      selectedTrackIndices = Array.from(checked).map(cb => parseInt(cb.value, 10));
      selectedTracksData = selectedTrackIndices
        .map(i => currentMediaData.tracks[i])
        .filter(Boolean);
    }

    progressBox.classList.remove('hidden');
    fileDownloadLink.classList.add('hidden');
    downloadBtn.disabled = true;

    updateProgressUI(5, 'Đang gửi yêu cầu đến máy chủ...', '0 KB/s', 'Đang tính toán');
    progressBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    showAlert('Đang khởi tạo tiến trình tải xuống...', 'info', false, 'Bắt đầu tải');

    try {
      const payload = {
        url: currentMediaData.url,
        platform: currentMediaData.platform,
        mode: currentMode,
        format: currentMode === 'audio' ? currentAudioFormat : currentVideoFormat,
        quality: currentMode === 'audio' ? currentAudioQuality : currentVideoQuality,
        selected_tracks: selectedTrackIndices,
        selected_items: selectedTracksData,
        title: currentMediaData.title
      };

      const res = await apiFetch('/api/download', {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify(payload)
      });

      let result;
      const resText = await res.text();
      try {
        result = JSON.parse(resText);
      } catch (e) {
        throw new Error('Lỗi phản hồi từ máy chủ khi tạo tác vụ tải.');
      }

      if (!res.ok || !result.success) {
        throw new Error(result.error || 'Khởi tạo quá trình tải thất bại.');
      }

      activeDownloadJobId = result.job_id;
      startProgressPolling(activeDownloadJobId);
    } catch (err) {
      console.error(err);
      showAlert(err.message, 'error');
      downloadBtn.disabled = false;
      progressBox.classList.add('hidden');
    }
  });

  async function cancelCurrentDownload() {
    const jobIdToCancel = activeDownloadJobId;

    if (progressPollingInterval) {
      clearInterval(progressPollingInterval);
      progressPollingInterval = null;
    }
    activeDownloadJobId = null;

    downloadBtn.disabled = false;
    progressBox.classList.add('hidden');
    fileDownloadLink.classList.add('hidden');

    showAlert('Đã hủy quá trình tải xuống!', 'warning', false, 'Đã hủy tải');

    if (jobIdToCancel) {
      try {
        await apiFetch('/api/cancel', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ job_id: jobIdToCancel })
        });
      } catch (err) {
        console.warn('Cancel error on backend:', err);
      }
    }
  }

  if (progressCancelBtn) {
    progressCancelBtn.addEventListener('click', cancelCurrentDownload);
  }

  function startProgressPolling(jobId) {
    if (progressPollingInterval) clearInterval(progressPollingInterval);

    progressPollingInterval = setInterval(async () => {
      try {
        const res = await apiFetch(`/api/progress?job_id=${encodeURIComponent(jobId)}`);
        const data = await res.json();

        if (!data.success) {
          clearInterval(progressPollingInterval);
          showAlert(data.error || 'Lỗi xử lý file.', 'error', false, 'Tải thất bại');
          downloadBtn.disabled = false;
          return;
        }

        updateProgressUI(
          data.percent || 10,
          data.status || 'Đang xử lý...',
          data.speed || '--',
          data.eta || '--'
        );

        if (data.finished) {
          clearInterval(progressPollingInterval);
          downloadBtn.disabled = false;

          updateProgressUI(100, 'Tải và xử lý hoàn tất! Đang lưu file...', 'Xong', '0s');

          if (data.download_url) {
            const fullDownloadUrl = data.download_url.startsWith('http') 
              ? data.download_url 
              : `${API_BASE}${data.download_url}`;

            let fileName = data.filename || 'media';
            if (!fileName.toLowerCase().startsWith('quoctinmedia')) {
              fileName = `QuocTinMedia - ${fileName}`;
            }
            fileDownloadLink.href = fullDownloadUrl;
            fileDownloadLink.setAttribute('download', fileName);
            fileDownloadLink.classList.remove('hidden');

            const hiddenIframe = document.createElement('iframe');
            hiddenIframe.style.display = 'none';
            hiddenIframe.src = fullDownloadUrl;
            document.body.appendChild(hiddenIframe);
            setTimeout(() => hiddenIframe.remove(), 10000);
            showAlert(currentMode === 'video' ? 'Đã tải video thành công với độ phân giải cao nhất!' : 'Đã tải bài hát thành công với chất lượng âm thanh cao nhất!', 'success', false, 'Tải thành công');
          }
        }
      } catch (err) {
        console.error('Polling error:', err);
      }
    }, 1200);
  }

  function updateProgressUI(percent, status, speed, eta) {
    const clamped = Math.min(Math.max(percent, 0), 100);
    progressBarFill.style.width = `${clamped}%`;
    progressPercent.textContent = `${Math.round(clamped)}%`;
    progressStatus.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> <span>${escapeHtml(status)}</span>`;
    progressSpeed.innerHTML = `<i class="fa-solid fa-gauge-high"></i> ${escapeHtml(speed)}`;
    progressETA.innerHTML = `<i class="fa-regular fa-clock"></i> Còn lại: ${escapeHtml(eta)}`;
  }

  async function checkServerHealth() {
    try {
      const res = await apiFetch('/api/health');
      if (res.ok) {
        if (backendStatus) {
          const dot = backendStatus.querySelector('.status-dot');
          if (dot) dot.className = 'status-dot online';
        }
        if (serverStatusText) {
          serverStatusText.textContent = 'Máy chủ: Hoạt động (YouTube, Spotify, SoundCloud, Zing MP3, NCT Sẵn sàng)';
        }
      } else {
        throw new Error('Not OK');
      }
    } catch {
      if (backendStatus) {
        const dot = backendStatus.querySelector('.status-dot');
        if (dot) dot.className = 'status-dot offline';
      }
      if (serverStatusText) {
        serverStatusText.textContent = 'Máy chủ: Chưa kết nối (Mở http://localhost:5500)';
      }
    }
  }

  function formatDuration(sec) {
    if (!sec || isNaN(sec)) return '--:--';
    sec = Math.round(sec);
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    const h = Math.floor(m / 60);
    const remM = m % 60;
    if (h > 0) {
      return `${h}:${remM.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
    }
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  function escapeHtml(text) {
    if (!text) return '';
    return text.replace(/[&<>"']/g, function(m) {
      switch (m) {
        case '&': return '&amp;';
        case '<': return '&lt;';
        case '>': return '&gt;';
        case '"': return '&quot;';
        default: return '&#039;';
      }
    });
  }

  // ==========================================
  // COOKIE MANAGEMENT LOGIC
  // ==========================================
  const cookieModal = document.getElementById('cookieModal');
  const cookieSettingsBtn = document.getElementById('cookieSettingsBtn');
  const closeCookieModalBtn = document.getElementById('closeCookieModalBtn');
  const closeCookieModalBtn2 = document.getElementById('closeCookieModalBtn2');
  const cookieBadgeDot = document.getElementById('cookieBadgeDot');
  const cookieModalStatusDot = document.getElementById('cookieModalStatusDot');
  const cookieStatusTitle = document.getElementById('cookieStatusTitle');
  const cookieStatusDesc = document.getElementById('cookieStatusDesc');
  const cookieDropzone = document.getElementById('cookieDropzone');
  const cookieFileInput = document.getElementById('cookieFileInput');
  const cookieTextarea = document.getElementById('cookieTextarea');
  const saveCookieTextBtn = document.getElementById('saveCookieTextBtn');
  const deleteCookieBtn = document.getElementById('deleteCookieBtn');

  function openCookieModal() {
    if (cookieModal) {
      cookieModal.classList.remove('hidden');
      refreshCookieStatus();
    }
  }

  function closeCookieModal() {
    if (cookieModal) {
      cookieModal.classList.add('hidden');
    }
  }

  if (cookieSettingsBtn) cookieSettingsBtn.addEventListener('click', openCookieModal);
  if (closeCookieModalBtn) closeCookieModalBtn.addEventListener('click', closeCookieModal);
  if (closeCookieModalBtn2) closeCookieModalBtn2.addEventListener('click', closeCookieModal);
  if (cookieModal) {
    cookieModal.addEventListener('click', (e) => {
      if (e.target === cookieModal) closeCookieModal();
    });
  }

  async function refreshCookieStatus() {
    try {
      const res = await fetch(`${API_BASE}/api/cookies/status`);
      const data = await res.json();
      if (data.has_cookies) {
        if (cookieBadgeDot) cookieBadgeDot.classList.add('has-file');
        if (cookieModalStatusDot) {
          cookieModalStatusDot.className = 'status-dot blue';
        }
        if (cookieStatusTitle) {
          cookieStatusTitle.textContent = `Đã nạp file ${data.filename} (${data.youtube_cookies || data.cookie_count} cookies)`;
        }
        if (cookieStatusDesc) {
          cookieStatusDesc.textContent = 'Hệ thống đang sử dụng cookie xác thực cá nhân của bạn để tải mọi video không giới hạn.';
        }
        if (deleteCookieBtn) deleteCookieBtn.classList.remove('hidden');
      } else {
        if (cookieBadgeDot) cookieBadgeDot.classList.remove('has-file');
        if (cookieModalStatusDot) {
          cookieModalStatusDot.className = 'status-dot green';
        }
        if (cookieStatusTitle) {
          cookieStatusTitle.textContent = 'Tự động chống Bot (web_embedded + mobile active)';
        }
        if (cookieStatusDesc) {
          cookieStatusDesc.textContent = 'Hệ thống đang tự động tối ưu hóa client để tải video YouTube không cần đăng nhập.';
        }
        if (deleteCookieBtn) deleteCookieBtn.classList.add('hidden');
      }
    } catch (err) {
      console.warn('Could not refresh cookie status:', err);
    }
  }

  refreshCookieStatus();

  if (cookieDropzone && cookieFileInput) {
    cookieDropzone.addEventListener('click', () => cookieFileInput.click());
    cookieDropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      cookieDropzone.classList.add('dragover');
    });
    cookieDropzone.addEventListener('dragleave', () => cookieDropzone.classList.remove('dragover'));
    cookieDropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      cookieDropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        uploadCookieFile(e.dataTransfer.files[0]);
      }
    });

    cookieFileInput.addEventListener('change', () => {
      if (cookieFileInput.files && cookieFileInput.files.length > 0) {
        uploadCookieFile(cookieFileInput.files[0]);
      }
    });
  }

  async function uploadCookieFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    try {
      const res = await fetch(`${API_BASE}/api/cookies/upload`, {
        method: 'POST',
        body: formData
      });
      const data = await res.json();
      if (data.success) {
        showAlert(data.message, 'success');
        refreshCookieStatus();
      } else {
        showAlert(data.error || 'Lỗi tải lên file cookie!', 'error');
      }
    } catch (err) {
      showAlert('Lỗi kết nối khi tải file cookie!', 'error');
    }
  }

  if (saveCookieTextBtn && cookieTextarea) {
    saveCookieTextBtn.addEventListener('click', async () => {
      const text = cookieTextarea.value.trim();
      if (!text) {
        showAlert('Vui lòng dán nội dung cookie trước khi lưu!', 'error');
        return;
      }
      try {
        saveCookieTextBtn.disabled = true;
        saveCookieTextBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Đang lưu...';
        const res = await fetch(`${API_BASE}/api/cookies/upload`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ cookies_text: text })
        });
        const data = await res.json();
        if (data.success) {
          showAlert(data.message, 'success');
          cookieTextarea.value = '';
          refreshCookieStatus();
        } else {
          showAlert(data.error || 'Lỗi lưu cookie!', 'error');
        }
      } catch (err) {
        showAlert('Lỗi kết nối khi lưu cookie!', 'error');
      } finally {
        saveCookieTextBtn.disabled = false;
        saveCookieTextBtn.innerHTML = '<i class="fa-solid fa-check"></i> Lưu Cookie';
      }
    });
  }

  if (deleteCookieBtn) {
    deleteCookieBtn.addEventListener('click', async () => {
      if (!confirm('Bạn có chắc chắn muốn xóa file cookies.txt không?')) return;
      try {
        const res = await fetch(`${API_BASE}/api/cookies/delete`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
          showAlert('Đã xóa cookies.txt. Hệ thống trở về chế độ tự động vượt Bot.', 'info');
          refreshCookieStatus();
        }
      } catch (err) {
        showAlert('Lỗi kết nối khi xóa cookie!', 'error');
      }
    });
  }

  // ==================== DONATE QR MODAL ====================
  const donateModal = document.getElementById('donateModal');
  const openDonateModalBtn = document.getElementById('openDonateModalBtn');
  const openDonateBannerBtn = document.getElementById('openDonateBannerBtn');
  const openDonateFooterBtn = document.getElementById('openDonateFooterBtn');
  const closeDonateModalBtn = document.getElementById('closeDonateModalBtn');
  const closeDonateModalBtn2 = document.getElementById('closeDonateModalBtn2');

  function openDonateModal() {
    if (donateModal) {
      donateModal.classList.remove('hidden');
      document.body.style.overflow = 'hidden';
    }
  }

  function closeDonateModal() {
    if (donateModal) {
      donateModal.classList.add('hidden');
      document.body.style.overflow = '';
    }
  }

  if (openDonateModalBtn) openDonateModalBtn.addEventListener('click', openDonateModal);
  if (openDonateBannerBtn) openDonateBannerBtn.addEventListener('click', openDonateModal);
  if (openDonateFooterBtn) openDonateFooterBtn.addEventListener('click', openDonateModal);

  if (closeDonateModalBtn) closeDonateModalBtn.addEventListener('click', closeDonateModal);
  if (closeDonateModalBtn2) closeDonateModalBtn2.addEventListener('click', closeDonateModal);

  if (donateModal) {
    donateModal.addEventListener('click', (e) => {
      if (e.target === donateModal) {
        closeDonateModal();
      }
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && donateModal && !donateModal.classList.contains('hidden')) {
      closeDonateModal();
    }
  });

  // ==================== CINEMATIC INTRO SPLASH ====================
  const introOverlay = document.getElementById('appIntroOverlay');
  const introProgressBar = document.getElementById('introProgressBar');
  const introStatusText = document.getElementById('introStatusText');
  const introPercent = document.getElementById('introPercent');
  const introSkipBtn = document.getElementById('introSkipBtn');

  if (introOverlay) {
    let currentP = 0;
    let introFinished = false;

    function finishIntro() {
      if (introFinished) return;
      introFinished = true;
      if (introProgressBar) introProgressBar.style.width = '100%';
      if (introPercent) introPercent.textContent = '100%';
      if (introStatusText) introStatusText.textContent = 'Hệ thống đã sẵn sàng!';
      setTimeout(() => {
        introOverlay.classList.add('intro-dismissed');
        setTimeout(() => {
          introOverlay.style.display = 'none';
        }, 650);
      }, 250);
    }

    if (introSkipBtn) {
      introSkipBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        finishIntro();
      });
    }

    introOverlay.addEventListener('click', () => {
      finishIntro();
    });

    const statusSteps = [
      { at: 15, text: 'Khởi tạo giao diện Studio...' },
      { at: 40, text: 'Nạp bộ giải mã YouTube & Spotify...' },
      { at: 70, text: 'Kích hoạt công nghệ âm thanh 320kbps...' },
      { at: 95, text: 'Chào mừng bạn đến với Quốc Tín Media Pro!' }
    ];

    const startTime = performance.now();
    const duration = 1400; // 1.4s total duration for a snappy, beautiful entrance

    function animateIntro(now) {
      if (introFinished) return;
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / duration);

      // Smooth easeOutCubic curve
      const eased = 1 - Math.pow(1 - progress, 3);
      currentP = Math.min(100, Math.floor(eased * 100));

      if (introProgressBar) introProgressBar.style.width = `${currentP}%`;
      if (introPercent) introPercent.textContent = `${currentP}%`;

      // Update status text
      for (let i = statusSteps.length - 1; i >= 0; i--) {
        if (currentP >= statusSteps[i].at) {
          if (introStatusText && introStatusText.textContent !== statusSteps[i].text) {
            introStatusText.textContent = statusSteps[i].text;
          }
          break;
        }
      }

      if (progress < 1) {
        requestAnimationFrame(animateIntro);
      } else {
        finishIntro();
      }
    }

    requestAnimationFrame(animateIntro);
  }

  // ==================== AUTHOR NOTICE BADGE ====================
  const authorNoticeBadge = document.getElementById('authorNoticeBadge');
  const closeAuthorNoticeBtn = document.getElementById('closeAuthorNoticeBtn');

  if (authorNoticeBadge && closeAuthorNoticeBtn) {
    closeAuthorNoticeBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      authorNoticeBadge.classList.add('dismissed');
      setTimeout(() => {
        authorNoticeBadge.style.display = 'none';
      }, 350);
    });
  }
});