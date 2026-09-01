# hosts/

Per-machine overrides, keyed by hostname (`hostnamectl hostname`, or
`run.sh --host <name>`).

    hosts/<hostname>/hypr/<name>.lua     appended after config/hypr/<name>.lua
    hosts/<hostname>/<file>              anything a module asks for via host_file

Keep behaviour here, not appearance: monitor scale, theme and bar layout are
tuned by hand on each machine and are deliberately not managed by this repo
(see the README's Non-goals).
