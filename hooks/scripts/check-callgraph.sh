#!/bin/bash
if ! command -v callgraph &>/dev/null; then
  echo "prism plugin: \`callgraph\` CLI not found. Install with: pip install -e ${CLAUDE_PLUGIN_ROOT}"
fi
exit 0
