# Algoritmo Centralizado de Exclusão Mútua Distribuída
Este repositório contém uma implementação em Python de um Algoritmo Centralizado de Exclusão Mútua para Sistemas Distribuídos. 

## Objetivo
O objetivo principal é garantir o acesso mutuamente exclusivo a um recurso compartilhado (Região Crítica), simulado aqui pela escrita concorrente e ordenada no arquivo resultado.txt, impedindo a ocorrência de condições de corrida e preservando a integridade dos dados.  O sistema adota o modelo Cliente-Servidor baseado em Sockets TCP estruturado sobre threads assíncronas.  