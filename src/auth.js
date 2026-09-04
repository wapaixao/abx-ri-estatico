function bypassAuthForLocalTest(){try{sessionStorage.setItem('abx_ri_auth','ok')}catch(e){}document.body.classList.remove('locked');const auth=document.getElementById('authScreen');if(auth)auth.style.display='none'}
function unlock(){const input=document.getElementById('passwordInput');bypassAuthForLocalTest();if(input)input.value='';render()}
function initAuth(){bypassAuthForLocalTest()}
