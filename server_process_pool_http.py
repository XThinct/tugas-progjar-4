from socket import *
import socket
import time
import sys
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from http import HttpServer

# Inisialisasi instance server HTTP global
http_server_instance = HttpServer()

def print_with_timestamp(message, level="INFO"):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    process_id = multiprocessing.current_process().pid
    
    if level == "INFO":
        print(f"[{timestamp}] [{process_id:>8}] {message}")
    elif level == "SUCCESS":
        print(f"[{timestamp}] [{process_id:>8}] {message}")
    elif level == "ERROR":
        print(f"[{timestamp}] [{process_id:>8}] {message}")
    elif level == "WARNING":
        print(f"[{timestamp}] [{process_id:>8}] {message}")
    elif level == "SERVER":
        print(f"[{timestamp}] [{'SERVER':>8}] {message}")
    elif level == "CLIENT":
        print(f"[{timestamp}] [{process_id:>8}] {message}")

def ProcessClientConnection(connection_info):
    """Menangani permintaan klien dalam proses terpisah - menerima data koneksi"""
    client_socket, client_address = connection_info
    
    try:
        print_with_timestamp(f"Memproses klien {client_address[0]}:{client_address[1]}", "CLIENT")
        
        # Membuat instance HttpServer baru untuk proses worker
        worker_http_server = HttpServer()
        
        request_buffer = ""
        while True:
            try:
                raw_data = client_socket.recv(4096)  # Buffer yang diperbesar untuk transfer file
                if raw_data:
                    # Mengubah bytes menjadi string untuk pemrosesan request
                    text_data = raw_data.decode('utf-8', errors='ignore')
                    request_buffer += text_data
                    
                    # Memverifikasi bahwa request HTTP lengkap telah diterima
                    if '\r\n\r\n' in request_buffer:
                        # Ekstrak method dan path untuk logging
                        first_line = request_buffer.split('\r\n')[0]
                        method_path = first_line.split(' ')[:2] if len(first_line.split(' ')) >= 2 else ['UNKNOWN', '/']
                        
                        print_with_timestamp(f"{client_address[0]}:{client_address[1]} → {method_path[0]} {method_path[1]}", "INFO")
                        
                        # Menangani request yang lengkap
                        server_response = worker_http_server.proses(request_buffer)
                        # Mengirim response kembali
                        client_socket.sendall(server_response)
                        
                        print_with_timestamp(f"Response dikirim ke {client_address[0]}:{client_address[1]}", "SUCCESS")
                        break
                    elif request_buffer.endswith('\r\n') and 'GET' in request_buffer and 'HTTP' in request_buffer:
                        # Ekstrak method dan path untuk logging
                        first_line = request_buffer.split('\r\n')[0]
                        method_path = first_line.split(' ')[:2] if len(first_line.split(' ')) >= 2 else ['UNKNOWN', '/']
                        
                        print_with_timestamp(f"{client_address[0]}:{client_address[1]} → {method_path[0]} {method_path[1]}", "INFO")
                        
                        # Menangani request GET sederhana
                        server_response = worker_http_server.proses(request_buffer)
                        client_socket.sendall(server_response)
                        
                        print_with_timestamp(f"Response dikirim ke {client_address[0]}:{client_address[1]}", "SUCCESS")
                        break
                else:
                    # Koneksi ditutup oleh klien
                    print_with_timestamp(f"Koneksi ditutup oleh {client_address[0]}:{client_address[1]}", "WARNING")
                    break
            except OSError as network_error:
                print_with_timestamp(f"Error koneksi dengan {client_address[0]}:{client_address[1]}: {network_error}", "ERROR")
                break
        
        client_socket.close()
        print_with_timestamp(f"Selesai menangani {client_address[0]}:{client_address[1]}", "SUCCESS")
        return f"Berhasil menangani klien {client_address}"
        
    except Exception as handling_error:
        print_with_timestamp(f"Error dalam ProcessClientConnection untuk {client_address[0]}:{client_address[1]}: {handling_error}", "ERROR")
        if client_socket:
            client_socket.close()
        return f"Error menangani {client_address}: {str(handling_error)}"

def print_server_status(active_processes):
    """Menampilkan status server secara berkala"""
    print(f"\n{'='*60}")
    print(f"SERVER STATUS - {datetime.now().strftime('%H:%M:%S')}")
    print(f"Active Processes: {active_processes}")
    print(f"Listening on: 172.16.16.101:8885")
    print(f"{'='*60}\n")

def InitializeServer():
    print_with_timestamp("Menginisialisasi Process Pool HTTP Server...", "SERVER")
    
    main_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    main_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    main_socket.bind(('172.16.16.101', 8885))
    main_socket.listen(10)
    
    print_with_timestamp("Process Pool HTTP Server aktif di port 8885", "SERVER")
    print_with_timestamp(f"Main Process ID: {multiprocessing.current_process().pid}", "SERVER")
    
    # Menyimpan daftar future yang sedang aktif untuk manajemen
    active_tasks = []
    last_status_time = time.time()
    
    with ProcessPoolExecutor(max_workers=4) as executor:
        try:
            while True:
                # Menampilkan status server setiap 30 detik jika ada aktivitas
                current_time = time.time()
                if current_time - last_status_time > 30 and active_tasks:
                    print_server_status(len(active_tasks))
                    last_status_time = current_time
                
                connection, address = main_socket.accept()
                print_with_timestamp(f"Koneksi baru diterima dari {address[0]}:{address[1]}", "SERVER")
                
                # Menghapus future yang sudah selesai dari tracking
                completed_tasks = [task for task in active_tasks if task.done()]
                for completed_task in completed_tasks:
                    try:
                        result = completed_task.result()
                        # Hasil sudah di-log di ProcessClientConnection, tidak perlu log lagi
                    except Exception as error:
                        print_with_timestamp(f"Task process gagal: {error}", "ERROR")
                    active_tasks.remove(completed_task)
                
                # Menambahkan task baru ke process pool
                future_task = executor.submit(ProcessClientConnection, (connection, address))
                active_tasks.append(future_task)
                
                print_with_timestamp(f"Process aktif: {len(active_tasks)}", "INFO")
                
        except KeyboardInterrupt:
            print_with_timestamp("Sinyal interrupt diterima. Mematikan server...", "WARNING")
            print_with_timestamp("Tekan Ctrl+C lagi untuk force shutdown", "WARNING")
            
            # Membiarkan process aktif untuk selesai
            if active_tasks:
                print_with_timestamp(f"Menunggu {len(active_tasks)} process aktif untuk selesai...", "INFO")
                try:
                    for done_future in as_completed(active_tasks, timeout=10):
                        try:
                            final_result = done_future.result()
                            # Hasil sudah di-log di ProcessClientConnection
                        except Exception as final_error:
                            print_with_timestamp(f"Error process: {final_error}", "ERROR")
                except TimeoutError:
                    print_with_timestamp("Timeout menunggu process selesai, force shutdown", "WARNING")
                    
        except Exception as error:
            print_with_timestamp(f"Server mengalami error: {error}", "ERROR")
        finally:
            print_with_timestamp("Menutup socket server...", "SERVER")
            main_socket.close()
            print_with_timestamp("Server telah dimatikan dengan aman", "SERVER")
            
            # Footer penutup
            print("\n" + "="*60)
            print("HTTP Process Pool Server - STOPPED")
            print("Terima kasih telah menggunakan server ini!")
            print("="*60)

def main_execution():
    # Penting: Mengkonfigurasi metode start multiprocessing
    if __name__ == "__main__":
        if sys.platform != 'win32':
            multiprocessing.set_start_method('fork', force=True)
        else:
            multiprocessing.set_start_method('spawn', force=True)
    
    InitializeServer()

if __name__ == "__main__":
    main_execution()