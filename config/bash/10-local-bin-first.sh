# Move $HOME/.local/bin ahead of /usr/bin in PATH.
#
# Omarchy's /usr/share/omarchy/default/bash/env-bootstrap deliberately *appends*
# ~/.local/bin so system binaries keep precedence. That means a local override
# such as ~/.local/bin/steam is never picked up. This reverses the order for
# ~/.local/bin only: it is inserted immediately before /usr/bin, so the mise
# shims (which come earlier) still win for mise-managed tools.
#
# Installed by omarchy-setup to ~/.config/bash/omarchy-setup/ and sourced from
# the fenced block in ~/.bashrc and from ~/.config/uwsm/env.d/90-local-bin-first.
# Idempotent: re-sourcing leaves PATH unchanged.

case ":$PATH:" in
  *":$HOME/.local/bin:"*)
    _lbf_new=''
    _lbf_placed=0
    _lbf_oifs=$IFS
    case $- in *f*) _lbf_glob=1 ;; *) _lbf_glob=0 ;; esac
    IFS=':'
    set -f
    for _lbf_dir in $PATH; do
      [ "$_lbf_dir" = "$HOME/.local/bin" ] && continue
      if [ "$_lbf_dir" = '/usr/bin' ] && [ "$_lbf_placed" -eq 0 ]; then
        _lbf_new="${_lbf_new:+$_lbf_new:}$HOME/.local/bin"
        _lbf_placed=1
      fi
      _lbf_new="${_lbf_new:+$_lbf_new:}$_lbf_dir"
    done
    IFS=$_lbf_oifs
    [ "$_lbf_glob" -eq 0 ] && set +f
    [ "$_lbf_placed" -eq 0 ] && _lbf_new="$HOME/.local/bin${_lbf_new:+:$_lbf_new}"
    PATH=$_lbf_new
    export PATH
    unset _lbf_new _lbf_placed _lbf_oifs _lbf_glob _lbf_dir
    ;;
esac
