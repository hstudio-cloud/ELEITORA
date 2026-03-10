#!/usr/bin/env node

/**
 * Cleanup legacy Portuguese-named files before build
 * This ensures Vercel doesn't pick up cached files from older deployments
 */

const fs = require('fs');
const path = require('path');

const LEGACY_PATTERNS = ['componentes', 'Componentes', 'FlutuanteFlora', 'flutuante', 'Flutuante'];
const SRC_DIR = path.join(__dirname, '../src');

function deletePath(targetPath) {
    try {
        if (!fs.existsSync(targetPath)) {
            return;
        }

        const stats = fs.lstatSync(targetPath);

        if (stats.isDirectory()) {
            // Recursively delete directory contents
            fs.readdirSync(targetPath).forEach(file => {
                deletePath(path.join(targetPath, file));
            });
            fs.rmdirSync(targetPath);
            console.log(`✓ Deleted directory: ${targetPath}`);
        } else {
            fs.unlinkSync(targetPath);
            console.log(`✓ Deleted file: ${targetPath}`);
        }
    } catch (error) {
        // Silently ignore errors
    }
}

function cleanupLegacyFiles(dir) {
    try {
        if (!fs.existsSync(dir)) {
            return;
        }

        const files = fs.readdirSync(dir);

        files.forEach(file => {
            const filePath = path.join(dir, file);
            const isLegacy = LEGACY_PATTERNS.some(pattern =>
                file.toLowerCase().includes(pattern.toLowerCase())
            );

            if (isLegacy) {
                deletePath(filePath);
            } else {
                const stats = fs.lstatSync(filePath);
                if (stats.isDirectory()) {
                    cleanupLegacyFiles(filePath);
                }
            }
        });
    } catch (error) {
        console.error(`Error processing directory ${dir}:`, error.message);
    }
}

console.log('🧹 Cleaning up legacy Portuguese-named files...');
cleanupLegacyFiles(SRC_DIR);
console.log('✅ Cleanup complete');
