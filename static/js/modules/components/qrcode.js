/**
 * Lightweight, zero-dependency QR Code Generator (ES Module)
 * Generates ISO/IEC 18004 compliant QR Codes as vector SVGs or HTML Canvas.
 */

// Galois Field arithmetic for GF(256) with primitive polynomial 0x11d
const QR_MATH = (() => {
  const expTable = new Uint8Array(256);
  const logTable = new Uint8Array(256);
  let x = 1;
  for (let i = 0; i < 255; i++) {
    expTable[i] = x;
    logTable[x] = i;
    x = (x << 1) ^ (x & 0x80 ? 0x11d : 0);
  }
  for (let i = 255; i < 512; i++) {
    expTable[i] = expTable[i - 255];
  }
  return {
    glog(n) {
      if (n < 1) throw new Error(`glog(${n})`);
      return logTable[n];
    },
    gexp(n) {
      while (n < 0) n += 255;
      while (n >= 256) n -= 255;
      return expTable[n];
    },
  };
})();

class QRPolynomial {
  constructor(num, shift = 0) {
    let offset = 0;
    while (offset < num.length && num[offset] === 0) {
      offset++;
    }
    this.num = new Uint8Array(num.length - offset + shift);
    for (let i = 0; i < num.length - offset; i++) {
      this.num[i] = num[offset + i];
    }
  }

  get(index) {
    return this.num[index];
  }

  getLength() {
    return this.num.length;
  }

  multiply(e) {
    const num = new Uint8Array(this.getLength() + e.getLength() - 1);
    for (let i = 0; i < this.getLength(); i++) {
      for (let j = 0; j < e.getLength(); j++) {
        num[i + j] ^= QR_MATH.gexp(QR_MATH.glog(this.get(i)) + QR_MATH.glog(e.get(j)));
      }
    }
    return new QRPolynomial(num);
  }

  mod(e) {
    if (this.getLength() - e.getLength() < 0) {
      return this;
    }
    const ratio = QR_MATH.glog(this.get(0)) - QR_MATH.glog(e.get(0));
    const num = new Uint8Array(this.getLength());
    for (let i = 0; i < this.getLength(); i++) {
      num[i] = this.get(i);
    }
    for (let i = 0; i < e.getLength(); i++) {
      num[i] ^= QR_MATH.gexp(QR_MATH.glog(e.get(i)) + ratio);
    }
    return new QRPolynomial(num).mod(e);
  }
}

// Error correction levels
export const QRECLevel = {
  L: 1, // 7% recovery
  M: 0, // 15% recovery
  Q: 3, // 25% recovery
  H: 2, // 30% recovery
};

// RS Block definitions [totalCodewords, dataCodewords, ecCodewordsPerBlock, numBlocksGroup1, dataCodewordsGroup1, numBlocksGroup2, dataCodewordsGroup2]
const RS_BLOCK_TABLE = [
  // 1
  [26, 19, 7, 1, 19, 0, 0], // L
  [26, 16, 10, 1, 16, 0, 0], // M
  [26, 13, 13, 1, 13, 0, 0], // Q
  [26, 9, 17, 1, 9, 0, 0], // H
  // 2
  [44, 34, 10, 1, 34, 0, 0], // L
  [44, 28, 16, 1, 28, 0, 0], // M
  [44, 22, 22, 1, 22, 0, 0], // Q
  [44, 16, 28, 1, 16, 0, 0], // H
  // 3
  [70, 55, 15, 1, 55, 0, 0], // L
  [70, 44, 26, 1, 44, 0, 0], // M
  [70, 34, 18, 2, 17, 0, 0], // Q
  [70, 26, 22, 2, 13, 0, 0], // H
  // 4
  [100, 80, 20, 1, 80, 0, 0], // L
  [100, 58, 18, 2, 29, 0, 0], // M
  [100, 48, 26, 2, 24, 0, 0], // Q
  [100, 36, 16, 4, 9, 0, 0], // H
  // 5
  [134, 108, 26, 1, 108, 0, 0], // L
  [134, 86, 24, 2, 43, 0, 0], // M
  [134, 62, 18, 2, 15, 2, 16], // Q
  [134, 46, 22, 2, 11, 2, 12], // H
  // 6
  [172, 136, 18, 2, 68, 0, 0], // L
  [172, 108, 16, 4, 27, 0, 0], // M
  [172, 76, 24, 4, 19, 0, 0], // Q
  [172, 60, 28, 4, 15, 0, 0], // H
  // 7
  [196, 156, 20, 2, 78, 0, 0], // L
  [196, 124, 18, 4, 31, 0, 0], // M
  [196, 88, 18, 2, 14, 4, 15], // Q
  [196, 66, 26, 4, 13, 1, 14], // H
  // 8
  [242, 194, 24, 2, 97, 0, 0], // L
  [242, 154, 22, 2, 38, 2, 39], // M
  [242, 110, 22, 4, 18, 2, 19], // Q
  [242, 86, 26, 4, 14, 2, 15], // H
  // 9
  [292, 232, 30, 2, 116, 0, 0], // L
  [292, 182, 22, 3, 36, 2, 37], // M
  [292, 132, 20, 4, 16, 4, 17], // Q
  [292, 100, 24, 4, 12, 4, 13], // H
  // 10
  [346, 274, 18, 2, 68, 2, 69], // L
  [346, 216, 26, 4, 43, 1, 44], // M
  [346, 154, 24, 6, 19, 2, 20], // Q
  [346, 122, 28, 6, 15, 2, 16], // H
];

const ALIGNMENT_PATTERN_TABLE = [
  [],
  [6, 18],
  [6, 22],
  [6, 26],
  [6, 30],
  [6, 34],
  [6, 22, 38],
  [6, 24, 42],
  [6, 26, 46],
  [6, 28, 50],
];

const FORMAT_INFO_TABLE = [
  0x77c4, 0x72f3, 0x7daa, 0x789d, 0x662f, 0x6318, 0x6c41, 0x6976, // L
  0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0, // M
  0x355f, 0x3068, 0x3f31, 0x3a06, 0x24b4, 0x2183, 0x2eda, 0x2bed, // Q
  0x1689, 0x13be, 0x1ce7, 0x19d0, 0x0762, 0x0255, 0x0d0c, 0x083b, // H
];

class QRBitBuffer {
  constructor() {
    this.buffer = [];
    this.length = 0;
  }

  get(index) {
    const bufIndex = Math.floor(index / 8);
    return ((this.buffer[bufIndex] >>> (7 - (index % 8))) & 1) === 1;
  }

  put(num, length) {
    for (let i = 0; i < length; i++) {
      this.putBit(((num >>> (length - i - 1)) & 1) === 1);
    }
  }

  putBit(bit) {
    const bufIndex = Math.floor(this.length / 8);
    if (this.buffer.length <= bufIndex) {
      this.buffer.push(0);
    }
    if (bit) {
      this.buffer[bufIndex] |= 0x80 >>> (this.length % 8);
    }
    this.length++;
  }
}

/**
 * Generate RS error correction polynomial of degree errorCount.
 */
function getErrorCorrectionPolynomial(errorCount) {
  let poly = new QRPolynomial([1]);
  for (let i = 0; i < errorCount; i++) {
    poly = poly.multiply(new QRPolynomial([1, QR_MATH.gexp(i)]));
  }
  return poly;
}

/**
 * Determine minimum QR version needed for given UTF-8 byte length.
 */
function getAutoVersion(dataByteLength, ecLevel) {
  for (let version = 1; version <= 10; version++) {
    const rowIdx = (version - 1) * 4 + ecLevel;
    const info = RS_BLOCK_TABLE[rowIdx];
    const dataCodewords = info[1];
    // 4 bits mode (8-bit byte = 0100) + 8 or 16 bits character count indicator
    const charCountBits = version < 10 ? 8 : 16;
    const headerBits = 4 + charCountBits;
    const maxBytes = Math.floor((dataCodewords * 8 - headerBits) / 8);
    if (dataByteLength <= maxBytes) {
      return version;
    }
  }
  return 10;
}

export class QRCode {
  constructor(version, ecLevel = QRECLevel.M) {
    this.version = version;
    this.ecLevel = ecLevel;
    this.moduleCount = version * 4 + 17;
    this.modules = Array.from({ length: this.moduleCount }, () => new Array(this.moduleCount).fill(null));
    this.dataList = [];
  }

  addData(data) {
    this.dataList.push(data);
  }

  make() {
    // 1. Encode data in byte mode
    const bytes = [];
    for (const item of this.dataList) {
      const str = String(item);
      const encoder = new TextEncoder();
      const utf8 = encoder.encode(str);
      for (let i = 0; i < utf8.length; i++) {
        bytes.push(utf8[i]);
      }
    }

    const rowIdx = (this.version - 1) * 4 + this.ecLevel;
    const blockInfo = RS_BLOCK_TABLE[rowIdx];
    const totalDataCodewords = blockInfo[1];
    const ecCodewordsPerBlock = blockInfo[2];

    const buffer = new QRBitBuffer();
    // Mode indicator: 8-bit byte is 0100 (4)
    buffer.put(4, 4);
    // Character count indicator
    buffer.put(bytes.length, this.version < 10 ? 8 : 16);
    for (const b of bytes) {
      buffer.put(b, 8);
    }

    // Terminator (up to 4 zeroes)
    const totalBits = totalDataCodewords * 8;
    for (let i = 0; i < 4 && buffer.length < totalBits; i++) {
      buffer.putBit(false);
    }

    // Pad to byte boundary
    while (buffer.length % 8 !== 0) {
      buffer.putBit(false);
    }

    // Pad bytes (0xEC, 0x11)
    const padBytes = [0xec, 0x11];
    let padIdx = 0;
    while (buffer.length < totalBits) {
      buffer.put(padBytes[padIdx % 2], 8);
      padIdx++;
    }

    // Split data into blocks and generate EC codewords
    const numBlocks1 = blockInfo[3];
    const dataLen1 = blockInfo[4];
    const numBlocks2 = blockInfo[5];
    const dataLen2 = blockInfo[6];
    const totalBlocks = numBlocks1 + numBlocks2;

    const dataBlocks = [];
    const ecBlocks = [];
    const ecPoly = getErrorCorrectionPolynomial(ecCodewordsPerBlock);

    let offset = 0;
    for (let i = 0; i < totalBlocks; i++) {
      const dataLen = i < numBlocks1 ? dataLen1 : dataLen2;
      const data = new Uint8Array(dataLen);
      for (let j = 0; j < dataLen; j++) {
        data[j] = buffer.buffer[offset++];
      }
      dataBlocks.push(data);

      const rawPoly = new QRPolynomial(data, ecCodewordsPerBlock);
      const modPoly = rawPoly.mod(ecPoly);
      const ecData = new Uint8Array(ecCodewordsPerBlock);
      const modLen = modPoly.getLength();
      for (let j = 0; j < ecCodewordsPerBlock; j++) {
        const modIdx = j + modLen - ecCodewordsPerBlock;
        ecData[j] = modIdx >= 0 ? modPoly.get(modIdx) : 0;
      }
      ecBlocks.push(ecData);
    }

    // Interleave data codewords
    const finalCodewords = [];
    const maxDataLen = Math.max(dataLen1, dataLen2);
    for (let j = 0; j < maxDataLen; j++) {
      for (let i = 0; i < totalBlocks; i++) {
        if (j < dataBlocks[i].length) {
          finalCodewords.push(dataBlocks[i][j]);
        }
      }
    }

    // Interleave error correction codewords
    for (let j = 0; j < ecCodewordsPerBlock; j++) {
      for (let i = 0; i < totalBlocks; i++) {
        finalCodewords.push(ecBlocks[i][j]);
      }
    }

    // 2. Setup matrix patterns
    this.setupPositionProbePattern(0, 0);
    this.setupPositionProbePattern(this.moduleCount - 7, 0);
    this.setupPositionProbePattern(0, this.moduleCount - 7);
    this.setupTimingPattern();
    this.setupAlignmentPattern();
    this.setupFormatInfo(true, 0);

    // 3. Map codewords into matrix
    const dataBitBuffer = new QRBitBuffer();
    for (const cw of finalCodewords) {
      dataBitBuffer.put(cw, 8);
    }

    // Remainder bits (for version 2-6 etc.)
    const remainderBits = [0, 7, 7, 7, 7, 7, 0, 0, 0, 0][this.version - 1] || 0;
    for (let i = 0; i < remainderBits; i++) {
      dataBitBuffer.putBit(false);
    }

    this.mapCodewords(dataBitBuffer);

    // 4. Select best mask pattern (0..7)
    let bestMask = 0;
    let minPenalty = Infinity;
    for (let mask = 0; mask < 8; mask++) {
      this.setupFormatInfo(false, mask);
      this.applyMask(mask);
      const penalty = this.getPenaltyScore();
      if (penalty < minPenalty) {
        minPenalty = penalty;
        bestMask = mask;
      }
      this.applyMask(mask); // revert mask
    }

    this.setupFormatInfo(false, bestMask);
    this.applyMask(bestMask);
  }

  setupPositionProbePattern(row, col) {
    for (let r = -1; r <= 7; r++) {
      for (let c = -1; c <= 7; c++) {
        const currR = row + r;
        const currC = col + c;
        if (currR < 0 || currR >= this.moduleCount || currC < 0 || currC >= this.moduleCount) {
          continue;
        }
        if (
          (0 <= r && r <= 6 && (c === 0 || c === 6)) ||
          (0 <= c && c <= 6 && (r === 0 || r === 6)) ||
          (2 <= r && r <= 4 && 2 <= c && c <= 4)
        ) {
          this.modules[currR][currC] = true;
        } else {
          this.modules[currR][currC] = false;
        }
      }
    }
  }

  setupTimingPattern() {
    for (let r = 8; r < this.moduleCount - 8; r++) {
      if (this.modules[r][6] === null) {
        this.modules[r][6] = r % 2 === 0;
      }
    }
    for (let c = 8; c < this.moduleCount - 8; c++) {
      if (this.modules[6][c] === null) {
        this.modules[6][c] = c % 2 === 0;
      }
    }
  }

  setupAlignmentPattern() {
    const pos = ALIGNMENT_PATTERN_TABLE[this.version - 1] || [];
    for (let i = 0; i < pos.length; i++) {
      for (let j = 0; j < pos.length; j++) {
        const row = pos[i];
        const col = pos[j];
        if (this.modules[row][col] !== null) continue;

        for (let r = -2; r <= 2; r++) {
          for (let c = -2; c <= 2; c++) {
            if (r === -2 || r === 2 || c === -2 || c === 2 || (r === 0 && c === 0)) {
              this.modules[row + r][col + c] = true;
            } else {
              this.modules[row + r][col + c] = false;
            }
          }
        }
      }
    }
  }

  setupFormatInfo(test, maskPattern) {
    const data = (this.ecLevel << 3) | maskPattern;
    const formatInfo = FORMAT_INFO_TABLE[data];

    for (let i = 0; i < 15; i++) {
      const bit = !test && ((formatInfo >> i) & 1) === 1;
      // Vertical
      if (i < 6) {
        this.modules[i][8] = bit;
      } else if (i < 8) {
        this.modules[i + 1][8] = bit;
      } else {
        this.modules[this.moduleCount - 15 + i][8] = bit;
      }

      // Horizontal
      if (i < 8) {
        this.modules[8][this.moduleCount - i - 1] = bit;
      } else if (i < 9) {
        this.modules[8][15 - i - 1 + 1] = bit;
      } else {
        this.modules[8][15 - i - 1] = bit;
      }
    }

    // Fixed dark module
    this.modules[this.moduleCount - 8][8] = !test;
  }

  mapCodewords(buffer) {
    let bitIdx = 0;
    let right = this.moduleCount - 1;
    let dir = -1;

    while (right > 0) {
      if (right === 6) right--; // Skip vertical timing column

      for (let vertical = 0; vertical < this.moduleCount; vertical++) {
        const r = dir === -1 ? this.moduleCount - 1 - vertical : vertical;
        for (let c = 0; c < 2; c++) {
          const col = right - c;
          if (this.modules[r][col] === null) {
            let bit = false;
            if (bitIdx < buffer.length) {
              bit = buffer.get(bitIdx);
              bitIdx++;
            }
            this.modules[r][col] = bit;
          }
        }
      }
      right -= 2;
      dir = -dir;
    }
  }

  applyMask(maskPattern) {
    for (let r = 0; r < this.moduleCount; r++) {
      for (let c = 0; c < this.moduleCount; c++) {
        if (this.isFunctionalModule(r, c)) continue;

        let mask = false;
        switch (maskPattern) {
          case 0:
            mask = (r + c) % 2 === 0;
            break;
          case 1:
            mask = r % 2 === 0;
            break;
          case 2:
            mask = c % 3 === 0;
            break;
          case 3:
            mask = (r + c) % 3 === 0;
            break;
          case 4:
            mask = (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0;
            break;
          case 5:
            mask = ((r * c) % 2) + ((r * c) % 3) === 0;
            break;
          case 6:
            mask = (((r * c) % 2) + ((r * c) % 3)) % 2 === 0;
            break;
          case 7:
            mask = (((r + c) % 2) + ((r * c) % 3)) % 2 === 0;
            break;
        }
        if (mask) {
          this.modules[r][c] = !this.modules[r][c];
        }
      }
    }
  }

  isFunctionalModule(r, c) {
    // Top-left finder
    if (r < 9 && c < 9) return true;
    // Top-right finder
    if (r < 9 && c >= this.moduleCount - 8) return true;
    // Bottom-left finder
    if (r >= this.moduleCount - 8 && c < 9) return true;
    // Timing patterns
    if (r === 6 || c === 6) return true;
    // Alignment patterns
    const pos = ALIGNMENT_PATTERN_TABLE[this.version - 1] || [];
    for (const pr of pos) {
      for (const pc of pos) {
        if (r >= pr - 2 && r <= pr + 2 && c >= pc - 2 && c <= pc + 2) {
          // If not overlapping with finders
          if (!(pr < 9 && pc < 9) && !(pr < 9 && pc >= this.moduleCount - 8) && !(pr >= this.moduleCount - 8 && pc < 9)) {
            return true;
          }
        }
      }
    }
    return false;
  }

  getPenaltyScore() {
    let penalty = 0;
    const n = this.moduleCount;

    // Feature 1: 5 or more same color adjacent in rows/cols
    for (let r = 0; r < n; r++) {
      let runColor = null;
      let runLen = 0;
      for (let c = 0; c < n; c++) {
        const color = this.modules[r][c];
        if (color === runColor) {
          runLen++;
        } else {
          if (runLen >= 5) penalty += 3 + (runLen - 5);
          runColor = color;
          runLen = 1;
        }
      }
      if (runLen >= 5) penalty += 3 + (runLen - 5);
    }

    for (let c = 0; c < n; c++) {
      let runColor = null;
      let runLen = 0;
      for (let r = 0; r < n; r++) {
        const color = this.modules[r][c];
        if (color === runColor) {
          runLen++;
        } else {
          if (runLen >= 5) penalty += 3 + (runLen - 5);
          runColor = color;
          runLen = 1;
        }
      }
      if (runLen >= 5) penalty += 3 + (runLen - 5);
    }

    // Feature 2: 2x2 blocks of same color
    for (let r = 0; r < n - 1; r++) {
      for (let c = 0; c < n - 1; c++) {
        const color = this.modules[r][c];
        if (
          color === this.modules[r + 1][c] &&
          color === this.modules[r][c + 1] &&
          color === this.modules[r + 1][c + 1]
        ) {
          penalty += 3;
        }
      }
    }

    // Feature 3: Finder-like patterns 1:1:3:1:1
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n - 6; c++) {
        if (
          this.modules[r][c] &&
          !this.modules[r][c + 1] &&
          this.modules[r][c + 2] &&
          this.modules[r][c + 3] &&
          this.modules[r][c + 4] &&
          !this.modules[r][c + 5] &&
          this.modules[r][c + 6]
        ) {
          if (c >= 4 && !this.modules[r][c - 1] && !this.modules[r][c - 2] && !this.modules[r][c - 3] && !this.modules[r][c - 4]) {
            penalty += 40;
          }
          if (c + 10 < n && !this.modules[r][c + 7] && !this.modules[r][c + 8] && !this.modules[r][c + 9] && !this.modules[r][c + 10]) {
            penalty += 40;
          }
        }
      }
    }

    // Feature 4: Proportion of dark modules
    let darkCount = 0;
    for (let r = 0; r < n; r++) {
      for (let c = 0; c < n; c++) {
        if (this.modules[r][c]) darkCount++;
      }
    }
    const ratio = (darkCount * 100) / (n * n);
    const k = Math.abs(Math.trunc((ratio - 50) / 5));
    penalty += k * 10;

    return penalty;
  }

  isDark(row, col) {
    return Boolean(this.modules[row][col]);
  }
}

/**
 * Generate a standalone SVG element representing the QR code.
 *
 * @param {string} text - Content to encode (e.g. challenge play URL).
 * @param {Object} [options]
 * @param {number} [options.margin=2] - Quiet zone margin in modules.
 * @param {number} [options.size=180] - Pixel size (width/height) of SVG.
 * @param {string} [options.color='#0f172a'] - Foreground module color.
 * @param {string} [options.background='#ffffff'] - Background color.
 * @param {number} [options.ecLevel=QRECLevel.M] - Error correction level.
 * @returns {SVGElement} - Constructed SVG DOM element.
 */
export function createQRCodeSvg(text, options = {}) {
  const {
    margin = 2,
    size = 180,
    color = "#0f172a",
    background = "#ffffff",
    ecLevel = QRECLevel.M,
  } = options;

  const encoder = new TextEncoder();
  const byteLen = encoder.encode(text).length;
  const version = getAutoVersion(byteLen, ecLevel);

  const qr = new QRCode(version, ecLevel);
  qr.addData(text);
  qr.make();

  const count = qr.moduleCount;
  const totalSize = count + margin * 2;

  // Build SVG string for crisp vector rendering
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${totalSize} ${totalSize}`);
  svg.setAttribute("width", String(size));
  svg.setAttribute("height", String(size));
  svg.setAttribute("shape-rendering", "crispEdges");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "QR Code");

  // Background rect
  if (background && background !== "transparent") {
    const bgRect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bgRect.setAttribute("width", String(totalSize));
    bgRect.setAttribute("height", String(totalSize));
    bgRect.setAttribute("fill", background);
    svg.appendChild(bgRect);
  }

  // Combined path data for minimal DOM nodes and optimal rendering performance
  let pathD = "";
  for (let r = 0; r < count; r++) {
    for (let c = 0; c < count; c++) {
      if (qr.isDark(r, c)) {
        const x = c + margin;
        const y = r + margin;
        pathD += `M${x},${y}h1v1h-1z `;
      }
    }
  }

  const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
  path.setAttribute("d", pathD.trim());
  path.setAttribute("fill", color);
  svg.appendChild(path);

  return svg;
}

/**
 * Render QR code directly inside a container element.
 *
 * @param {HTMLElement} container - Target container to inject QR code into.
 * @param {string} text - Content URL or string.
 * @param {Object} [options] - Options passed to createQRCodeSvg.
 */
export function renderQRCode(container, text, options = {}) {
  if (!container) return;
  container.innerHTML = "";
  if (!text) return;
  const svg = createQRCodeSvg(text, options);
  container.appendChild(svg);
}
