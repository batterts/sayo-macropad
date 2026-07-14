" SayoDevice ↔ vim integration (Stage 1: recording state)
" Polls vim's recording state 5x/sec and pushes it to the keyboard on change,
" via sayo_state.py (wear-free cmd-16 color channel). Uses polling instead of the
" RecordingEnter/Leave autocmds because some MacVim builds lack those events.
"
" Add to your ~/.vimrc:
let g:sayo_py   = '/Users/shaun.batterton/code/SayoDevice-Shauny-GPT-version/venv/bin/python'
let g:sayo_tool = '/Users/shaun.batterton/code/SayoDevice-Shauny-GPT-version/sayo_state.py'
let g:sayo_last = -1
function! SayoPoll(timer)
  let l:rec = empty(reg_recording()) ? 0 : 1
  if l:rec != g:sayo_last
    let g:sayo_last = l:rec
    call job_start([g:sayo_py, g:sayo_tool, string(l:rec)])
  endif
endfunction
call timer_start(200, 'SayoPoll', {'repeat': -1})
