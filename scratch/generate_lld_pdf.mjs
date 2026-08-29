import fs from 'node:fs';

const OUT = 'D:\\EdTech Prjct\\AfrazLLD_normal_LLD_style.pdf';
const W = 595.28;
const H = 841.89;
const M = 56;
const contentW = W - M * 2;
const headerY = H - 42;
const footerY = 34;
const topY = H - 76;
const bottomY = 74;

function esc(value) {
  return String(value)
    .replace(/\\/g, '\\\\')
    .replace(/\(/g, '\\(')
    .replace(/\)/g, '\\)')
    .replace(/[\r\n]/g, ' ');
}

function estimateWidth(text, size, font = 'F1') {
  let width = 0;
  for (const ch of String(text)) {
    if (ch === ' ') width += 0.25;
    else if ('il.,:;!|'.includes(ch)) width += 0.23;
    else if ('mwMW@#%'.includes(ch)) width += 0.78;
    else if ('ABCDEFGHIJKLMNOPQRSTUVWXYZ'.includes(ch)) width += 0.58;
    else if ('0123456789'.includes(ch)) width += 0.5;
    else width += font === 'F4' ? 0.58 : 0.5;
  }
  return width * size;
}

function wrapText(text, maxWidth, size, font = 'F1') {
  const lines = [];
  for (const paragraph of String(text).split('\n')) {
    if (!paragraph.trim()) {
      lines.push('');
      continue;
    }
    let line = '';
    for (const word of paragraph.split(/\s+/)) {
      const candidate = line ? `${line} ${word}` : word;
      if (estimateWidth(candidate, size, font) <= maxWidth) {
        line = candidate;
      } else {
        if (line) lines.push(line);
        line = word;
      }
    }
    if (line) lines.push(line);
  }
  return lines;
}

class Page {
  constructor(number) {
    this.number = number;
    this.ops = [];
    this.y = topY;
  }

  op(value) {
    this.ops.push(value);
  }

  line(x1, y1, x2, y2, width = 0.7) {
    this.op(`0 0 0 RG ${width} w ${x1.toFixed(2)} ${y1.toFixed(2)} m ${x2.toFixed(2)} ${y2.toFixed(2)} l S`);
  }

  rect(x, y, w, h, fill = false, stroke = true, gray = null) {
    if (gray !== null) this.op(`${gray} ${gray} ${gray} rg`);
    this.op(`${x.toFixed(2)} ${y.toFixed(2)} ${w.toFixed(2)} ${h.toFixed(2)} re ${fill && stroke ? 'B' : fill ? 'f' : 'S'}`);
    if (gray !== null) this.op('0 0 0 rg');
  }

  text(value, x, y, size = 11, font = 'F1', align = 'left') {
    let xx = x;
    if (align === 'center') xx -= estimateWidth(value, size, font) / 2;
    if (align === 'right') xx -= estimateWidth(value, size, font);
    this.op(`BT /${font} ${size.toFixed(2)} Tf ${xx.toFixed(2)} ${y.toFixed(2)} Td (${esc(value)}) Tj ET`);
  }

  wrapped(value, x, width, size = 10.6, font = 'F1', leading = 13.2, after = 8) {
    for (const line of wrapText(value, width, size, font)) {
      this.text(line, x, this.y, size, font);
      this.y -= leading;
    }
    this.y -= after;
  }

  h1(value) {
    this.y -= 4;
    this.text(value.toUpperCase(), M, this.y, 15.5, 'F2');
    this.y -= 8;
    this.line(M, this.y, W - M, this.y, 1.2);
    this.y -= 18;
  }

  h2(value) {
    this.text(value, M, this.y, 13, 'F2');
    this.y -= 18;
  }

  h3(value) {
    this.text(value, M, this.y, 11.5, 'F2');
    this.y -= 16;
  }

  p(value, after = 9) {
    this.wrapped(value, M, contentW, 10.6, 'F1', 13.2, after);
  }

  italic(value, after = 10) {
    this.wrapped(value, M, contentW, 10.3, 'F3', 13, after);
  }

  bullets(items, indent = 18, after = 7) {
    for (const item of items) {
      const lines = wrapText(item, contentW - indent - 14, 10.35, 'F1');
      this.text('-', M + indent, this.y, 10.35, 'F1');
      this.text(lines[0] || '', M + indent + 14, this.y, 10.35, 'F1');
      this.y -= 13;
      for (const line of lines.slice(1)) {
        this.text(line, M + indent + 14, this.y, 10.35, 'F1');
        this.y -= 13;
      }
    }
    this.y -= after;
  }

  code(lines, after = 10) {
    this.y -= 2;
    for (const line of lines) {
      this.text(line, M + 34, this.y, 9, 'F4');
      this.y -= 11;
    }
    this.y -= after;
  }

  table(columns, rows, widths, compact = false) {
    const padX = 6;
    const lineH = compact ? 10.2 : 11.2;
    const fontSize = compact ? 8.6 : 9.2;
    const headerSize = compact ? 9.1 : 9.8;
    const padTop = compact ? 9 : 11;
    const padBottom = compact ? 5 : 6;
    const rowHeight = (cells, header = false) => {
      let maxLines = 1;
      for (let i = 0; i < cells.length; i += 1) {
        maxLines = Math.max(maxLines, wrapText(cells[i], widths[i] - padX * 2, header ? headerSize : fontSize, header ? 'F2' : 'F1').length);
      }
      return Math.max(header ? 21 : compact ? 18 : 22, maxLines * lineH + padTop + padBottom);
    };
    const drawRow = (cells, height, header = false, shade = false) => {
      const tableWidth = widths.reduce((sum, value) => sum + value, 0);
      if (header || shade) this.rect(M, this.y - height, tableWidth, height, true, false, header ? '0.88' : '0.96');
      let x = M;
      for (const width of widths) {
        this.line(x, this.y, x, this.y - height, 0.45);
        x += width;
      }
      this.line(x, this.y, x, this.y - height, 0.45);
      this.line(M, this.y, x, this.y, 0.45);
      this.line(M, this.y - height, x, this.y - height, 0.45);
      x = M;
      for (let i = 0; i < cells.length; i += 1) {
        const font = header ? 'F2' : 'F1';
        const size = header ? headerSize : fontSize;
        let ty = this.y - padTop;
        for (const line of wrapText(cells[i], widths[i] - padX * 2, size, font)) {
          this.text(line, x + padX, ty, size, font);
          ty -= lineH;
        }
        x += widths[i];
      }
      this.y -= height;
    };
    drawRow(columns, rowHeight(columns, true), true);
    rows.forEach((row, index) => drawRow(row, rowHeight(row), false, index % 2 === 0));
    this.y -= compact ? 10 : 14;
  }
}

const pages = [];

function headerFooter(page) {
}

function newPage() {
  const page = new Page(pages.length + 1);
  headerFooter(page);
  pages.push(page);
  return page;
}

function toc(page, level, title, pageNumber) {
  const x = M + (level - 1) * 18;
  const size = level === 1 ? 10.6 : 10.2;
  const font = level === 1 ? 'F2' : 'F1';
  page.text(title, x, page.y, size, font);
  const pageString = String(pageNumber);
  const endX = W - M - estimateWidth(pageString, size, font) - 4;
  const startX = x + estimateWidth(title, size, font) + 6;
  for (let dx = startX; dx < endX; dx += 4.8) page.text('.', dx, page.y, size, font);
  page.text(pageString, W - M, page.y, size, font, 'right');
  page.y -= level === 1 ? 18 : 16;
}

let page = newPage();
page.y = H - 92;
page.text('TABLE OF CONTENTS', W / 2, page.y, 16, 'F2', 'center');
page.y -= 38;
[
  [1, '1. Introduction', 2],
  [1, '2. Database Design & Data Dictionary', 2],
  [2, '2.1 Table: users', 2],
  [2, '2.2 Table: blocks', 3],
  [2, '2.3 Table: campus_directory', 3],
  [2, '2.4 Table: nodes', 4],
  [1, '3. Component-Level Design', 4],
  [2, '3.1 Authentication Module (hashvera.routes.auth)', 4],
  [2, '3.2 Blockchain & Records Module', 5],
  [2, '3.3 P2P Network API (hashvera.routes.api)', 5],
  [2, '3.4 Administrative Module (hashvera.routes.admin)', 5],
  [1, '4. Utility Class & Function Signatures', 6],
  [2, '4.1 Security Utilities (hashvera.utils.hashing)', 6],
  [2, '4.2 Database Access Objects (DAO) (hashvera.database)', 6],
  [1, '5. State Machine & Logic Flow', 6],
  [2, '5.1 Record Request State Machine', 6],
  [1, '6. Error Dictionary & Exception Handling', 6],
].forEach((row) => toc(page, ...row));

page = newPage();
page.h1('1. Introduction');
page.p('This Low-Level Design (LLD) document specifies the exact technical architecture of the HashVera application at the component, class, and method level. It serves as a blueprint for developers to understand the granular implementation details of the modular Flask blueprints, SQLite schema, and internal utility functions.');
page.y -= 12;
page.h1('2. Database Design & Data Dictionary');
page.p('The system uses an embedded SQLite database. Below are the exhaustive schema details, including constraints, default values, and indexes.');
page.h2('2.1 Table: users');
page.p('Purpose: Stores application user accounts and authentication materials.');
page.table(['Field Name', 'Data Type', 'Constraints', 'Default', 'Description'], [
  ['id', 'INTEGER', 'PK, AUTOINCREMENT', '', 'Internal user identifier.'],
  ['username', 'TEXT', 'UNIQUE, NOT NULL', '', 'Alphanumeric login handle.'],
  ['campus_id', 'TEXT', 'UNIQUE', '', 'External institutional ID.'],
  ['email', 'TEXT', 'UNIQUE', '', 'Contact and recovery email.'],
  ['password_hash', 'TEXT', 'NOT NULL', '', 'PBKDF2 hash of password.'],
  ['password_salt', 'TEXT', 'NOT NULL', '', '32-byte cryptographic salt.'],
  ['role', 'TEXT', 'NOT NULL', '', 'Student / Faculty / Exam Cell / Administrator.'],
  ['force_password_change', 'INTEGER', 'DEFAULT 0', '0', 'Boolean flag; forces reset on login.'],
  ['disabled', 'INTEGER', 'DEFAULT 0', '0', 'Boolean flag for soft-deletion.'],
  ['last_login_at', 'TEXT', '', '', 'ISO-8601 timestamp of last auth.'],
], [104, 68, 105, 58, 117]);
page.italic('Indexes: idx_users_email, idx_users_campus_id', 12);
page.h2('2.2 Table: blocks');
page.p('Purpose: Represents the immutable ledger of academic records.');

page = newPage();
page.h2('2.2 Table: blocks');
page.table(['Field Name', 'Data Type', 'Constraints', 'Default', 'Description'], [
  ['id', 'INTEGER', 'PK, AUTOINCREMENT', '', 'Internal table ID.'],
  ['block_index', 'INTEGER', 'UNIQUE, NOT NULL', '', 'Chain sequence number. Genesis = 0.'],
  ['timestamp', 'TEXT', 'NOT NULL', '', 'ISO-8601 time of minting.'],
  ['payload', 'TEXT', 'NOT NULL', '', 'JSON string of academic data.'],
  ['previous_hash', 'TEXT', 'NOT NULL', '', 'SHA-256 hash of block at index-1.'],
  ['block_hash', 'TEXT', 'NOT NULL', '', 'Computed SHA-256 hash of this block.'],
  ['nonce', 'TEXT', 'NOT NULL', '', 'Cryptographic salt for hash randomization.'],
  ['owner', 'TEXT', 'NOT NULL', '', 'Username of the student owner.'],
  ['certificate_id', 'TEXT', 'INDEXED', '', '16-char public verification token.'],
  ['block_signature', 'TEXT', '', '', 'HMAC signature from the minting node.'],
], [88, 64, 108, 58, 170], true);
page.italic('Indexes: idx_blocks_certificate_id', 10);
page.h2('2.3 Table: campus_directory');
page.p('Purpose: Ground-truth table containing pre-authorized institutional members.', 6);
page.table(['Field Name', 'Data Type', 'Constraints', 'Default', 'Description'], [
  ['id', 'INTEGER', 'PK, AUTOINCREMENT', '', 'Internal ID.'],
  ['campus_id', 'TEXT', 'UNIQUE, NOT NULL', '', 'Institutional ID.'],
  ['full_name', 'TEXT', 'NOT NULL', '', 'Legal name of the member.'],
  ['campus_email', 'TEXT', 'UNIQUE, NOT NULL', '', 'Institutional email address.'],
  ['is_registered', 'INTEGER', 'DEFAULT 0', '0', 'Flag if users table record exists.'],
], [88, 64, 108, 58, 170], true);

page = newPage();
page.h2('2.4 Table: nodes');
page.p('Purpose: Registry of authorized peer nodes for decentralized synchronization.', 6);
page.table(['Field Name', 'Data Type', 'Constraints', 'Default', 'Description'], [
  ['id', 'INTEGER', 'PK, AUTOINCREMENT', '', 'Internal ID.'],
  ['name', 'TEXT', 'UNIQUE, NOT NULL', '', 'Node identifier (e.g., Node-Alpha).'],
  ['peer_url', 'TEXT', '', '', 'FQDN or IP of the peer.'],
  ['api_token', 'TEXT', '', '', 'Bearer token for /api access.'],
  ['signing_secret', 'TEXT', '', '', 'HMAC secret to verify peer blocks.'],
  ['is_active', 'INTEGER', 'DEFAULT 1', '1', 'Boolean toggle for sync inclusion.'],
], [88, 64, 108, 58, 170], true);
page.h1('3. Component-Level Design');
page.h2('3.1 Authentication Module (hashvera.routes.auth)');
page.p('This Blueprint handles session lifecycles and identity verification.');
page.h3('Controllers / Routes');
page.text('GET /login', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Checks if session.get(\'user_id\') exists. If true, redirects to /dashboard.', 'Renders auth/login.html.']);
page.text('POST /login', M, page.y, 10.4, 'F4');
page.y -= 15;
page.italic('Inputs: login_id (username or email), password.', 2);
page.text('Logic:', M, page.y, 10.4, 'F1');
page.y -= 14;
page.bullets(['Query users where username = login_id OR email = login_id.', 'Extract password_salt and password_hash.', 'Call hash_password(input_password, salt).', 'Constant-time compare hashes.', 'Check if disabled == 1. If so, throw AccountDisabledError.', 'Establish session[\'user_id\'], session[\'role\'], session[\'username\'].'], 18, 5);
page.text('GET /logout', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Executes session.clear().', 'Redirects to /login.'], 18, 0);

page = newPage();
page.h2('3.2 Blockchain & Records Module');
page.p('This component manages the cryptographic state of the application.');
page.h3('Logic Flow: add_record(payload_dict, owner_username, file_path=None)');
page.bullets(['Acquire Lock: SQLite handles connection locking; logical locking required for concurrency.', 'Retrieve Previous Block: SELECT * FROM blocks ORDER BY block_index DESC LIMIT 1.', 'Calculate Index: new_index = prev_block.block_index + 1.', 'Serialize Payload: json_str = json.dumps(payload_dict, sort_keys=True).', 'Generate Nonce: nonce = os.urandom(16).hex().', 'Compute Hash: data_string = str(new_index) + timestamp + json_str + prev_block.block_hash + nonce; block_hash = hashlib.sha256(data_string.encode()).hexdigest().', 'Sign Block: signature = hmac.new(NODE_SECRET, block_hash, hashlib.sha256).hexdigest().', 'Persist: Execute INSERT INTO blocks.']);
page.h2('3.3 P2P Network API (hashvera.routes.api)');
page.p('This Blueprint exposes endpoints for inter-node communication. It uses a token-based authentication decorator @require_api_token.');
page.h3('Endpoints');
page.text('GET /api/v1/chain/info', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Logic: Returns JSON with the maximum block_index and the block_hash of that index.', 'Response: {"status": "ok", "length": 150, "latest_hash": "a1b2..."}'], 18, 3);
page.text('GET /api/v1/chain/blocks', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Params: ?from_index=<int>', 'Logic: SELECT * FROM blocks WHERE block_index >= ? ORDER BY block_index ASC.', 'Response: JSON array of block dictionary objects.'], 18, 7);
page.h2('3.4 Administrative Module (hashvera.routes.admin)');
page.p('Restricted via @require_role(\'Administrator\').', 4);
page.h3('Controllers / Routes');
page.text('GET /admin/users', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Renders a paginated view of the users table, joined with campus_directory to show registration status.'], 18, 3);
page.text('POST /admin/users/<id>/toggle', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Flips the disabled boolean flag in the database.', 'Creates an entry in audit_logs.'], 18, 3);
page.text('POST /admin/bulk-mint', M, page.y, 10.4, 'F4');
page.y -= 15;
page.bullets(['Parses uploaded CSV file.', 'Iterates rows; validates campus_id.', 'Wraps a loop of add_record() calls in a DB transaction (conn.commit() only at the end).', 'Rolls back if any single record fails validation to prevent chain forks.'], 18, 0);

page = newPage();
page.h1('4. Utility Class & Function Signatures');
page.h2('4.1 Security Utilities (hashvera.utils.hashing)');
page.code(['def hash_password(password: str, salt: str = None) -> tuple[str, str]:', '    """', '    Applies PBKDF2 with SHA-256 to the input password.', '    If salt is None, generates a 32-byte secure random salt.', '    Returns: (hex_encoded_hash, hex_encoded_salt)', '    """'], 4);
page.code(['def verify_hmac_signature(payload_string: str, signature: str, secret_key: str) -> bool:', '    """', '    Performs a constant-time comparison of the provided signature against', '    a newly generated HMAC-SHA256 signature of the payload.', '    """'], 8);
page.h2('4.2 Database Access Objects (DAO) (hashvera.database)');
page.code(['def get_connection() -> sqlite3.Connection:', '    """', '    Returns a configured SQLite3 connection with row_factory set to sqlite3.Row', '    and foreign key constraints enabled via PRAGMA.', '    """', '', 'def execute_write(query: str, params: tuple) -> int:', '    """', '    Executes a modifying query and auto-commits. Returns the lastrowid.', '    """'], 8);
page.h1('5. State Machine & Logic Flow');
page.h2('5.1 Record Request State Machine');
page.p('The lifecycle of a student\'s request to have a document minted on the blockchain:', 6);
page.table(['Pending', '->', 'Approved', '->', 'Minted'], [['Student submits', '', 'Faculty reviews', '', 'Exam Cell mints']], [116, 36, 116, 36, 116], true);
page.table(['Pending', '->', 'Rejected'], [['Student submits', '', 'Faculty denies']], [180, 40, 180], true);
page.italic('Implementation Context: State transitions are handled in hashvera.routes.records, updating the status column in the record_requests table.', 10);
page.h1('6. Error Dictionary & Exception Handling');
page.p('The application maps specific internal states to standard HTTP responses to ensure the frontend and API consumers can react appropriately.');

function buildPdf(documentPages) {
  const objects = [];
  const add = (body) => {
    objects.push(body);
    return objects.length;
  };
  const font1 = add('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman >>');
  const font2 = add('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Bold >>');
  const font3 = add('<< /Type /Font /Subtype /Type1 /BaseFont /Times-Italic >>');
  const font4 = add('<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>');
  const contentIds = documentPages.map((documentPage) => {
    const stream = `${documentPage.ops.join('\n')}\n`;
    return add(`<< /Length ${Buffer.byteLength(stream, 'latin1')} >>\nstream\n${stream}endstream`);
  });
  const pagesId = 4 + contentIds.length + documentPages.length + 1;
  const pageIds = contentIds.map((contentId) =>
    add(`<< /Type /Page /Parent ${pagesId} 0 R /MediaBox [0 0 ${W.toFixed(2)} ${H.toFixed(2)}] /Resources << /Font << /F1 ${font1} 0 R /F2 ${font2} 0 R /F3 ${font3} 0 R /F4 ${font4} 0 R >> >> /Contents ${contentId} 0 R >>`)
  );
  const actualPagesId = add(`<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${documentPages.length} >>`);
  const catalogId = add(`<< /Type /Catalog /Pages ${actualPagesId} 0 R >>`);
  let pdf = '%PDF-1.4\n%\xE2\xE3\xCF\xD3\n';
  const offsets = [0];
  for (let i = 0; i < objects.length; i += 1) {
    offsets.push(Buffer.byteLength(pdf, 'latin1'));
    pdf += `${i + 1} 0 obj\n${objects[i]}\nendobj\n`;
  }
  const xref = Buffer.byteLength(pdf, 'latin1');
  pdf += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (let i = 1; i < offsets.length; i += 1) pdf += `${String(offsets[i]).padStart(10, '0')} 00000 n \n`;
  pdf += `trailer\n<< /Size ${objects.length + 1} /Root ${catalogId} 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(pdf, 'latin1');
}

const bounds = pages.map((documentPage) => ({ page: documentPage.number, finalY: Math.round(documentPage.y), belowBottom: documentPage.y < bottomY }));
if (bounds.some((entry) => entry.belowBottom)) {
  throw new Error(`Layout overflow: ${JSON.stringify(bounds)}`);
}

fs.writeFileSync(OUT, buildPdf(pages));
console.log(JSON.stringify({ out: OUT, pages: pages.length, bounds }, null, 2));
