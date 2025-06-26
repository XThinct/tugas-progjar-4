import sys
import os.path
import uuid
from glob import glob
from datetime import datetime
import urllib.parse
import json

class HttpServer:
	def __init__(self):
		self.sessions = {}
		self.types = {
			'.pdf': 'application/pdf',
			'.jpg': 'image/jpeg',
			'.txt': 'text/plain',
			'.html': 'text/html'
		}
		
	def response(self, kode=404, message='Not Found', messagebody=bytes(), headers={}):
		current_time = datetime.now().strftime('%c')
		response_lines = []
		
		# Membuat baris status HTTP
		response_lines.append(f"HTTP/1.0 {kode} {message}\r\n")
		response_lines.append(f"Date: {current_time}\r\n")
		response_lines.append("Connection: close\r\n")
		response_lines.append("Server: myserver/1.0\r\n")
		response_lines.append(f"Content-Length: {len(messagebody)}\r\n")
		
		# Menambahkan header tambahan
		for header_key in headers:
			response_lines.append(f"{header_key}:{headers[header_key]}\r\n")
		
		response_lines.append("\r\n")
		
		# Menggabungkan semua header menjadi string
		header_string = ''.join(response_lines)
		
		# Memastikan messagebody dalam format bytes
		if not isinstance(messagebody, bytes):
			messagebody = messagebody.encode()
		
		# Menggabungkan header dan body
		final_response = header_string.encode() + messagebody
		return final_response
		
	def parse_multipart_data(self, body, boundary):
		"""Mengurai data multipart form untuk upload file"""
		boundary_bytes = ('--' + boundary).encode()
		data_parts = body.split(boundary_bytes)
		uploaded_files = {}
		
		for part in data_parts:
			if b'Content-Disposition' in part:
				part_lines = part.split(b'\r\n')
				disposition_header = None
				file_name = None
				
				# Mencari header Content-Disposition
				for line in part_lines:
					if b'Content-Disposition' in line:
						disposition_header = line.decode()
						if 'filename=' in disposition_header:
							file_name = disposition_header.split('filename=')[1].strip('"')
						break
				
				if file_name:
					# Mencari lokasi data file (setelah header kosong)
					content_start = part.find(b'\r\n\r\n')
					if content_start != -1:
						file_content = part[content_start + 4:]
						# Menghapus trailing boundary
						if file_content.endswith(b'\r\n'):
							file_content = file_content[:-2]
						uploaded_files[file_name] = file_content
		
		return uploaded_files
		
	def proses(self, data):
		request_lines = data.split("\r\n")
		first_line = request_lines[0]
		header_lines = [line for line in request_lines[1:] if line != '']
		
		# Ekstrak body untuk request POST
		request_body = ""
		if "\r\n\r\n" in data:
			body_index = data.find("\r\n\r\n") + 4
			request_body = data[body_index:]
		
		line_parts = first_line.split(" ")
		try:
			http_method = line_parts[0].upper().strip()
			requested_path = line_parts[1].strip()
			
			if http_method == 'GET':
				return self.http_get(requested_path, header_lines)
			elif http_method == 'POST':
				return self.http_post(requested_path, header_lines, request_body)
			elif http_method == 'DELETE':
				return self.http_delete(requested_path, header_lines)
			else:
				return self.response(400, 'Bad Request', '', {})
		except IndexError:
			return self.response(400, 'Bad Request', '', {})
			
	def http_get(self, object_address, headers):
		available_files = glob('./*')
		base_directory = './'
		
		# Route untuk halaman utama
		if object_address == '/':
			return self.response(200, 'OK', 'Ini Adalah web Server percobaan', {})
		
		# Route untuk redirect video
		if object_address == '/video':
			return self.response(302, 'Found', '', {'location': 'https://youtu.be/katoxpnTf04'})
		
		# Route santai
		if object_address == '/santai':
			return self.response(200, 'OK', 'santai saja', {})
		
		# Route untuk menampilkan daftar file
		if object_address == '/files':
			return self.list_directory_files(base_directory)
		
		# Menangani request file
		file_path = object_address[1:]  # Menghapus '/' di awal
		full_path = base_directory + file_path
		
		if full_path not in available_files:
			return self.response(404, 'Not Found', '', {})
		
		# Membaca file dalam mode binary
		with open(full_path, 'rb') as file_handle:
			file_content = file_handle.read()
		
		# Menentukan content type berdasarkan ekstensi file
		file_extension = os.path.splitext(full_path)[1]
		mime_type = self.types.get(file_extension, 'application/octet-stream')
		
		response_headers = {'Content-type': mime_type}
		return self.response(200, 'OK', file_content, response_headers)
		
	def list_directory_files(self, directory):
		"""Menampilkan daftar semua file dalam direktori"""
		try:
			file_list = []
			for item in os.listdir(directory):
				item_path = os.path.join(directory, item)
				if os.path.isfile(item_path):
					file_details = {
						'name': item,
						'size': os.path.getsize(item_path),
						'modified': datetime.fromtimestamp(os.path.getmtime(item_path)).strftime('%Y-%m-%d %H:%M:%S')
					}
					file_list.append(file_details)
			
			# Membuat konten HTML
			html_template = """
			<!DOCTYPE html>
			<html>
			<head>
				<title>Directory Listing</title>
				<style>
					table { border-collapse: collapse; width: 100%; }
					th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
					th { background-color: #f2f2f2; }
				</style>
			</head>
			<body>
				<h1>Directory Files</h1>
				<table>
					<tr>
						<th>File Name</th>
						<th>Size (bytes)</th>
						<th>Last Modified</th>
					</tr>
			"""
			
			# Menambahkan baris untuk setiap file
			for file_info in file_list:
				html_template += f"""
					<tr>
						<td>{file_info['name']}</td>
						<td>{file_info['size']}</td>
						<td>{file_info['modified']}</td>
					</tr>
				"""
			
			html_template += """
				</table>
				<br>
				<h2>Upload File</h2>
				<form action="/upload" method="post" enctype="multipart/form-data">
					<input type="file" name="file" required>
					<input type="submit" value="Upload">
				</form>
			</body>
			</html>
			"""
			
			response_headers = {'Content-type': 'text/html'}
			return self.response(200, 'OK', html_template, response_headers)
			
		except Exception as error:
			return self.response(500, 'Internal Server Error', f'Error listing directory: {str(error)}', {})
	
	def http_post(self, object_address, headers, body):
		# Menangani upload file
		if object_address == '/upload':
			return self.handle_file_upload(headers, body)
		
		# Default response untuk POST request lainnya
		response_headers = {}
		content = "kosong"
		return self.response(200, 'OK', content, response_headers)
		
	def handle_file_upload(self, headers, body):
		"""Menangani upload file dari form multipart"""
		try:
			# Mencari header Content-Type untuk mendapatkan boundary
			content_type_line = None
			for header_line in headers:
				if header_line.lower().startswith('content-type:'):
					content_type_line = header_line
					break
			
			if not content_type_line or 'multipart/form-data' not in content_type_line:
				return self.response(400, 'Bad Request', 'Invalid content type for file upload', {})
			
			# Ekstrak boundary dari header
			boundary_value = None
			if 'boundary=' in content_type_line:
				boundary_value = content_type_line.split('boundary=')[1].strip()
			
			if not boundary_value:
				return self.response(400, 'Bad Request', 'Missing boundary in multipart data', {})
			
			# Parse data multipart
			body_bytes = body.encode() if isinstance(body, str) else body
			parsed_files = self.parse_multipart_data(body_bytes, boundary_value)
			
			if not parsed_files:
				return self.response(400, 'Bad Request', 'No file found in upload', {})
			
			# Menyimpan file yang diupload
			saved_files = []
			for filename, file_data in parsed_files.items():
				try:
					file_path = './' + filename
					with open(file_path, 'wb') as output_file:
						output_file.write(file_data)
					saved_files.append(filename)
				except Exception as save_error:
					return self.response(500, 'Internal Server Error', f'Error saving file {filename}: {str(save_error)}', {})
			
			# Membuat response HTML
			success_html = f"""
			<!DOCTYPE html>
			<html>
			<body>
				<h1>Upload Successful</h1>
				<p>Files uploaded: {', '.join(saved_files)}</p>
				<a href="/files">Back to file list</a>
			</body>
			</html>
			"""
			
			response_headers = {'Content-type': 'text/html'}
			return self.response(200, 'OK', success_html, response_headers)
			
		except Exception as upload_error:
			return self.response(500, 'Internal Server Error', f'Upload error: {str(upload_error)}', {})
	
	def http_delete(self, object_address, headers):
		"""Menangani penghapusan file"""
		try:
			# Ekstrak nama file dari URL (format: /delete/filename)
			if not object_address.startswith('/delete/'):
				return self.response(400, 'Bad Request', 'Invalid delete URL format. Use /delete/filename', {})
			
			target_filename = object_address[8:]  # Menghapus prefix '/delete/'
			if not target_filename:
				return self.response(400, 'Bad Request', 'No filename specified', {})
			
			# Decode URL-encoded filename
			decoded_filename = urllib.parse.unquote(target_filename)
			target_path = './' + decoded_filename
			
			# Validasi keberadaan file
			if not os.path.exists(target_path):
				return self.response(404, 'Not Found', f'File {decoded_filename} not found', {})
			
			if not os.path.isfile(target_path):
				return self.response(400, 'Bad Request', f'{decoded_filename} is not a file', {})
			
			# Menghapus file
			os.remove(target_path)
			
			# Membuat response HTML
			delete_success_html = f"""
			<!DOCTYPE html>
			<html>
			<body>
				<h1>Delete Successful</h1>
				<p>File '{decoded_filename}' has been deleted.</p>
				<a href="/files">Back to file list</a>
			</body>
			</html>
			"""
			
			response_headers = {'Content-type': 'text/html'}
			return self.response(200, 'OK', delete_success_html, response_headers)
			
		except Exception as delete_error:
			return self.response(500, 'Internal Server Error', f'Delete error: {str(delete_error)}', {})

# Testing section
if __name__ == "__main__":
	httpserver = HttpServer()
	test_response1 = httpserver.proses('GET testing.txt HTTP/1.0')
	print(test_response1)
	test_response2 = httpserver.proses('GET donalbebek.jpg HTTP/1.0')
	print(test_response2)