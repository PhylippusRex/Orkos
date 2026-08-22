// Compiles contracts/Orkos.sol, writes ABI + bytecode to contracts/
const fs = require("fs");
const path = require("path");
const solc = require("solc");

const contractPath = path.join(__dirname, "..", "contracts", "Orkos.sol");
const source = fs.readFileSync(contractPath, "utf8");

const input = {
  language: "Solidity",
  sources: { "Orkos.sol": { content: source } },
  settings: {
    outputSelection: { "*": { "*": ["abi", "evm.bytecode.object"] } },
    optimizer: { enabled: true, runs: 200 },
  },
};

const output = JSON.parse(solc.compile(JSON.stringify(input)));

if (output.errors) {
  const fatal = output.errors.filter((e) => e.severity === "error");
  output.errors.forEach((e) => console.log(e.formattedMessage));
  if (fatal.length > 0) {
    console.error(`\n${fatal.length} compile error(s). Aborting.`);
    process.exit(1);
  }
}

const contract = output.contracts["Orkos.sol"]["Orkos"];
const abi = contract.abi;
const bytecode = contract.evm.bytecode.object;

fs.writeFileSync(
  path.join(__dirname, "..", "contracts", "Orkos.abi.json"),
  JSON.stringify(abi, null, 2)
);
fs.writeFileSync(
  path.join(__dirname, "..", "contracts", "Orkos.bytecode.txt"),
  bytecode
);

console.log("Compiled successfully.");
console.log(`ABI:      contracts/Orkos.abi.json (${abi.length} entries)`);
console.log(`Bytecode: contracts/Orkos.bytecode.txt (${bytecode.length} chars)`);
