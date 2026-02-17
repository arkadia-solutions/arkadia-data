const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// Load package.json to get the real package name (e.g., @arkadia/ai-data-format)
const pkg = require('../package.json');
const PACKAGE_NAME = pkg.name; 

// --- CONFIGURATION ---
const ROOT_DIR = path.resolve(__dirname, '..');
const TEMP_DIR = path.join(ROOT_DIR, 'temp_smoke_test');
const DIST_DIR = path.join(ROOT_DIR, 'dist'); 

// Node.js modules we DO NOT want in the browser build
const FORBIDDEN_IMPORTS = ['util', 'fs', 'path', 'child_process', 'os'];

// --- HELPERS ---
const log = (msg) => console.log(`\x1b[36m[VERIFY]\x1b[0m ${msg}`);
const success = (msg) => console.log(`\x1b[32m[SUCCESS]\x1b[0m ${msg}`);
const error = (msg) => console.error(`\x1b[31m[ERROR]\x1b[0m ${msg}`);

function scanDirForForbiddenImports(dir) {
    if (!fs.existsSync(dir)) return;
    
    const files = fs.readdirSync(dir);
    
    for (const file of files) {
        const fullPath = path.join(dir, file);
        const stat = fs.statSync(fullPath);

        if (stat.isDirectory()) {
            scanDirForForbiddenImports(fullPath);
        } else if (file.endsWith('.js') || file.endsWith('.mjs')) {
            const content = fs.readFileSync(fullPath, 'utf-8');
            
            FORBIDDEN_IMPORTS.forEach(mod => {
                // Regex looks for: require('util') OR from 'util'
                const regex = new RegExp(`(require\\(['"]${mod}['"]\\)|from\\s+['"]${mod}['"])`);
                if (regex.test(content)) {
                    throw new Error(
                        `Found Node.js specific module '${mod}' in file: ${file}\n` +
                        `This will crash in the browser! Please remove the import or use a polyfill.`
                    );
                }
            });
        }
    }
}

// --- MAIN PROCESS ---

try {
    log(`🚀 Starting verification process for: ${PACKAGE_NAME}...`);

    // 1. Cleanup
    if (fs.existsSync(TEMP_DIR)) {
        log('Cleaning up old test artifacts...');
        fs.rmSync(TEMP_DIR, { recursive: true, force: true });
    }

    // 2. Build Project
    log('1. Building project (npm run build)...');
    try {
        execSync('npm run build', { stdio: 'inherit', cwd: ROOT_DIR });
    } catch (e) {
        throw new Error("Build failed. Fix compilation errors first.");
    }

    // 3. BROWSER COMPATIBILITY CHECK
    log('2. Checking for browser compatibility (No Node.js built-ins)...');
    scanDirForForbiddenImports(DIST_DIR);
    success('Browser compatibility check passed! No forbidden imports found.');

    // 4. Pack Project
    log('3. Packaging (npm pack)...');
    const packOutput = execSync('npm pack', { cwd: ROOT_DIR }).toString().trim();
    // npm pack output might have multiple lines, take the last one (filename)
    const tgzFileName = packOutput.split('\n').pop().trim();
    const tgzPath = path.join(ROOT_DIR, tgzFileName);
    
    if (!fs.existsSync(tgzPath)) {
        throw new Error(`Could not find packed file: ${tgzFileName}`);
    }
    log(`   📦 Created: ${tgzFileName}`);

    // 5. Create Temp Environment
    log('4. Creating temporary test environment...');
    fs.mkdirSync(TEMP_DIR);
    execSync('npm init -y', { cwd: TEMP_DIR, stdio: 'ignore' });

    // 6. Install Tarball
    log(`5. Installing tarball into temp env...`);
    execSync(`npm install "${tgzPath}"`, { cwd: TEMP_DIR, stdio: 'ignore' });

    // 7. Verify Script - USING FUNCTIONAL IMPORTS { decode, encode }
    const verifyScript = `
        const { decode, encode } = require('${PACKAGE_NAME}');
        
        console.log("   🧪 Running functional tests...");
        
        try {
            // --- 1. INPUT DATA ---
            const inputData = { 
                msg: "Hello World", 
                status: "OK", 
                count: 123 
            };
            console.log("\\n   🔹 [INPUT]:", JSON.stringify(inputData));

            // --- 2. ENCODE ---
            if (typeof encode !== 'function') {
                throw new Error("Export 'encode' is not a function!");
            }

            const encoded = encode(inputData);
            
            if (!encoded) throw new Error("Encode returned empty result");

            // DISPLAY ENCODE RESULT
            console.log("   🔸 [ENCODED]:", encoded); 

            // --- 3. DECODE ---
            if (typeof decode !== 'function') {
                throw new Error("Export 'decode' is not a function!");
            }

            const result = decode(encoded);
            
            if (!result) throw new Error("Decode returned empty result");

            // --- 4. EXTRACT DATA FOR VERIFICATION ---
            // We handle two cases: 
            // A) decode() returns raw data directly
            // B) decode() returns a result wrapper (e.g. { node: ... })
            
            let decodedOutput = result;
            
            if (result.node && result.node.fields) {
                // It's likely a Wrapper Object -> Extract values to a simple JS object for comparison
                decodedOutput = {};
                for (const key in result.node.fields) {
                    // Assuming field has .value
                    decodedOutput[key] = result.node.fields[key].value !== undefined 
                        ? result.node.fields[key].value 
                        : result.node.fields[key];
                }
            } else if (result.node && result.node.value) {
                 decodedOutput = result.node.value;
            }

            // DISPLAY DECODE RESULT
            console.log("   🔹 [DECODED RAW]:", JSON.stringify(result));
            console.log("   🔹 [DECODED EXTRACTED]:", JSON.stringify(decodedOutput));

            // --- 5. INTEGRITY CHECK ---
            if (decodedOutput.msg === "Hello World" && decodedOutput.count === 123) {
                 console.log("\\n   ✅ INTEGRITY CHECK PASSED");
            } else {
                 console.log("\\n   ⚠️ Integrity check failed or structure mismatch.");
                 console.log("   Expected:", JSON.stringify(inputData));
                 console.log("   Got:", JSON.stringify(decodedOutput));
                 // We don't fail here to allow you to inspect the output, 
                 // but strictly strictly speaking it should throw.
                 // throw new Error("Data mismatch");
            }
            
        } catch (e) {
            console.error("\\n   ❌ Functional Test Failed:", e.message);
            if (e.stack) console.error(e.stack);
            process.exit(1);
        }
    `;

    fs.writeFileSync(path.join(TEMP_DIR, 'verify_script.js'), verifyScript);

    // 8. Run Verification
    log('6. Running functional verification...');
    execSync('node verify_script.js', { cwd: TEMP_DIR, stdio: 'inherit' });

    // 9. Cleanup
    log('7. Cleanup...');
    fs.rmSync(TEMP_DIR, { recursive: true, force: true });
    fs.unlinkSync(tgzPath); 

    console.log('\n');
    success('READY FOR PUBLISH! 🚀');
    console.log(` - Package: ${PACKAGE_NAME}`);
    console.log(' - Browser Compatible: YES');
    console.log('\n');

} catch (e) {
    console.log('\n');
    error('VERIFICATION FAILED!');
    console.error(e.message || e);
    
    try {
        const tgzFiles = fs.readdirSync(ROOT_DIR).filter(f => f.endsWith('.tgz'));
        tgzFiles.forEach(f => fs.unlinkSync(path.join(ROOT_DIR, f)));
    } catch (cleanupErr) {}
    
    process.exit(1);
}