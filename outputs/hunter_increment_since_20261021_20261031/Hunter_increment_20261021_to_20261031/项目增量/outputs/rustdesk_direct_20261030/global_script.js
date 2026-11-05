// Personal RustDesk direct rule; active when Clash runs in rule mode.
function main(config, profileName) {
  const rule = 'PROCESS-NAME,RustDesk.exe,DIRECT';
  if (!config || !Array.isArray(config.rules)) return config;
  config.rules = [rule].concat(config.rules.filter(item => item !== rule));
  return config;
}
