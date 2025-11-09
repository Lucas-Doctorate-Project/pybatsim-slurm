# schedSlurm.py
from batsim.batsim import BatsimScheduler, Batsim, Job
from procset import ProcSet
import math
import operator
from collections import defaultdict

class SchedSlurm(BatsimScheduler):
    def __init__(self, options):
        super().__init__(options)
        
        # Fatores de prioridade (pesos)
        self.priority_weight_age = options.get('priority_weight_age', 1000)
        self.priority_weight_job_size = options.get('priority_weight_job_size', 1000)
        self.priority_weight_fairshare = options.get('priority_weight_fairshare', 10000)
        self.priority_weight_partition = options.get('priority_weight_partition', 1000)
        self.priority_weight_qos = options.get('priority_weight_qos', 0)
        
        # Configurações
        self.priority_max_age = options.get('priority_max_age', 14 * 24 * 3600)  # 14 dias em segundos
        self.priority_favor_small = options.get('priority_favor_small', False)
        self.sched_delay = options.get('sched_delay', 0.005)
        
        # Estado interno
        self.pending_jobs = []
        self.running_jobs = []
        self.available_resources = None
        self.total_resources = 0
        
        # Para cálculo de fairshare (simplificado)
        self.user_usage = defaultdict(float)
        self.user_shares = defaultdict(float)
        self.total_usage = 0.0
        
        # Partições (simuladas)
        self.partitions = {
            "default": {"priority": 10, "resources": None},
            "high": {"priority": 20, "resources": None}
        }

    def onAfterBatsimInit(self):
        """Inicializa recursos após início do Batsim"""
        self.total_resources = self.bs.nb_compute_resources
        self.available_resources = ProcSet((0, self.total_resources - 1))
        
        # Distribui recursos entre partições (exemplo simples)
        half = self.total_resources // 2
        self.partitions["default"]["resources"] = ProcSet((0, half - 1))
        self.partitions["high"]["resources"] = ProcSet((half, self.total_resources - 1))

    def onSimulationBegins(self):
        """Chamado quando a simulação inicia"""
        self.logger.info(f"SlurmScheduler iniciado com {self.total_resources} recursos")
        self.logger.info(f"Pesos - Age: {self.priority_weight_age}, "
                        f"JobSize: {self.priority_weight_job_size}, "
                        f"Fairshare: {self.priority_weight_fairshare}")

    def calculate_job_priority(self, job, current_time):
        """Calcula a prioridade do job usando fatores multifator similares ao SLURM"""
        
        # Fator Idade
        wait_time = current_time - job.submit_time
        age_factor = min(1.0, wait_time / self.priority_max_age)
        
        # Fator Tamanho do Job
        if self.priority_favor_small:
            job_size_factor = 1.0 - (job.requested_resources / self.total_resources)
        else:
            job_size_factor = job.requested_resources / self.total_resources
        
        # Fator Fairshare (simplificado)
        user = job.id.split('!')[0] if '!' in job.id else "default"
        fairshare_factor = self.calculate_fairshare_factor(user)
        
        # Fator Partição (simplificado - assumindo partição 'high' para alguns jobs)
        partition = self.determine_partition(job)
        partition_priority = self.partitions[partition]["priority"]
        max_partition_priority = max(p["priority"] for p in self.partitions.values())
        partition_factor = partition_priority / max_partition_priority
        
        # Cálculo da prioridade final
        priority = (
            self.priority_weight_age * age_factor +
            self.priority_weight_job_size * job_size_factor +
            self.priority_weight_fairshare * fairshare_factor +
            self.priority_weight_partition * partition_factor
        )
        
        return priority

    def determine_partition(self, job):
        """Determina a partição para um job baseado em suas características"""
        # Exemplo simples: jobs grandes ou com walltime alto vão para partição high
        if (job.requested_resources > self.total_resources * 0.3 or 
            (hasattr(job, 'requested_time') and job.requested_time > 3600)):
            return "high"
        return "default"

    def calculate_fairshare_factor(self, user):
        """Calcula fator fairshare simplificado"""
        if self.total_usage == 0:
            return 1.0
        
        # Share alvo (igual para todos os usuários neste exemplo simples)
        target_share = 1.0 / len(self.user_shares) if self.user_shares else 1.0
        
        # Uso normalizado
        normalized_usage = self.user_usage[user] / self.total_usage if self.total_usage > 0 else 0
        
        # Fator fairshare (usuários abaixo da cota têm prioridade mais alta)
        fairshare_factor = max(0.0, target_share - normalized_usage)
        return fairshare_factor

    def update_usage_stats(self, job, current_time):
        """Atualiza estatísticas de uso para cálculo de fairshare"""
        user = job.id.split('!')[0] if '!' in job.id else "default"
        
        if job.job_state == Job.State.RUNNING:
            # Simula uso durante execução
            runtime = current_time - (getattr(job, 'start_time', current_time))
            usage = job.requested_resources * runtime
            self.user_usage[user] += usage
            self.total_usage += usage

    def allocate_resources_for_job(self, job):
        """Aloca recursos para um job considerando partições"""
        partition = self.determine_partition(job)
        partition_resources = self.partitions[partition]["resources"]
        
        # Recursos disponíveis na partição
        available_in_partition = self.available_resources & partition_resources
        
        if len(available_in_partition) >= job.requested_resources:
            # Aloca os primeiros recursos disponíveis na partição
            allocation = ProcSet(*list(available_in_partition)[:job.requested_resources])
            return allocation
        return None

    def schedule(self):
        """Executa o algoritmo de escalonamento"""
        current_time = self.bs.time()
        
        # Consome tempo de escalonamento
        self.bs.consume_time(self.sched_delay)
        
        if not self.pending_jobs:
            return

        # Calcula prioridades para todos os jobs pendentes
        job_priorities = []
        for job in self.pending_jobs:
            priority = self.calculate_job_priority(job, current_time)
            job_priorities.append((job, priority))
        
        # Ordena jobs por prioridade (decrescente)
        job_priorities.sort(key=operator.itemgetter(1), reverse=True)
        
        scheduled_jobs = []
        for job, priority in job_priorities:
            if len(self.available_resources) >= job.requested_resources:
                allocation = self.allocate_resources_for_job(job)
                if allocation:
                    job.allocation = allocation
                    self.available_resources -= allocation
                    scheduled_jobs.append(job)
                    self.pending_jobs.remove(job)
                    
                    # Registra tempo de início para cálculo de fairshare
                    job.start_time = current_time
        
        # Executa jobs escalonados
        if scheduled_jobs:
            self.bs.execute_jobs(scheduled_jobs)
            self.running_jobs.extend(scheduled_jobs)
            
            self.logger.info(f"Escalonados {len(scheduled_jobs)} jobs, "
                           f"Recursos disponíveis: {len(self.available_resources)}/{self.total_resources}")

    def onJobSubmission(self, job):
        """Chamado quando um job é submetido"""
        self.logger.info(f"Job submetido: {job.id}, Recursos: {job.requested_resources}")
        
        # Verifica se o job pode ser executado no sistema
        if job.requested_resources > self.total_resources:
            self.bs.reject_jobs([job])
            self.logger.warning(f"Job {job.id} rejeitado: solicita mais recursos que o total disponível")
            return
        
        # Adiciona à lista de pendentes e tenta escalonar
        self.pending_jobs.append(job)
        self.schedule()

    def onJobCompletion(self, job):
        """Chamado quando um job é completado"""
        self.logger.info(f"Job completado: {job.id}, Estado: {job.job_state}")
        
        # Libera recursos
        if job.allocation:
            self.available_resources |= job.allocation
        
        # Remove das listas
        if job in self.running_jobs:
            self.running_jobs.remove(job)
        if job in self.pending_jobs:
            self.pending_jobs.remove(job)
        
        # Atualiza estatísticas de uso
        current_time = self.bs.time()
        self.update_usage_stats(job, current_time)
        
        # Re-escalona jobs pendentes
        self.schedule()

    def onJobMessage(self, timestamp, job, message):
        """Chamado quando uma mensagem é recebida de um job"""
        self.logger.info(f"Mensagem do job {job.id}: {message}")

    def onJobsKilled(self, jobs):
        """Chamado quando jobs são mortos"""
        for job in jobs:
            self.logger.info(f"Job morto: {job.id}")
            if job.allocation:
                self.available_resources |= job.allocation
            if job in self.running_jobs:
                self.running_jobs.remove(job)
            if job in self.pending_jobs:
                self.pending_jobs.remove(job)
        
        self.schedule()

    def onNoMoreExternalEvents(self):
        """Chamado quando não há mais eventos externos"""
        self.logger.info("Não há mais eventos externos - finalizando escalonamento")

    def onSimulationEnds(self):
        """Chamado quando a simulação termina"""
        self.logger.info("Simulação finalizada")
        self.logger.info(f"Jobs pendentes: {len(self.pending_jobs)}")
        self.logger.info(f"Jobs executando: {len(self.running_jobs)}")
        self.logger.info(f"Estatísticas de uso: {dict(self.user_usage)}")
